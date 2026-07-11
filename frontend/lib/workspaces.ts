/**
 * Workspace persistence — server-first with a localStorage fallback.
 *
 * Each analysis is saved as a "workspace" so users get history and can reopen
 * past runs. Records are stored server-side (Redis-backed, shared across
 * browsers/devices) and mirrored to localStorage so the app keeps working
 * when the backend is unreachable and older local-only workspaces stay
 * accessible.
 */

import type { ProcessResponse } from "./types";
import type { ChatMessage } from "@/components/chat/MessageBubble";
import type { QueryResult } from "@/components/workspace/CanvasPane";
import { api } from "./api";

const INDEX_KEY = "io-ws-index";
const recordKey = (id: string) => `io-ws-${id}`;
const MAX_WORKSPACES = 25;

export interface SavedState {
    analysisResult: ProcessResponse | null;
    messages: ChatMessage[];
    results: QueryResult[];
    pinned: number[];
}

export interface WorkspaceMeta {
    id: string;
    datasetName: string;
    filePath: string;
    createdAt: number;
    updatedAt: number;
}

export interface WorkspaceRecord extends WorkspaceMeta {
    state: SavedState;
}

// ── localStorage layer (offline cache / fallback) ───────────────────────────

function readIndex(): WorkspaceMeta[] {
    if (typeof window === "undefined") return [];
    try {
        return JSON.parse(localStorage.getItem(INDEX_KEY) ?? "[]");
    } catch {
        return [];
    }
}

function writeIndex(index: WorkspaceMeta[]) {
    localStorage.setItem(INDEX_KEY, JSON.stringify(index));
}

function localList(): WorkspaceMeta[] {
    return readIndex().sort((a, b) => b.updatedAt - a.updatedAt);
}

function localLoad(id: string): WorkspaceRecord | null {
    try {
        const raw = localStorage.getItem(recordKey(id));
        return raw ? (JSON.parse(raw) as WorkspaceRecord) : null;
    } catch {
        return null;
    }
}

function localDelete(id: string) {
    localStorage.removeItem(recordKey(id));
    writeIndex(readIndex().filter((w) => w.id !== id));
}

/**
 * Upsert into localStorage. Handles quota by evicting the oldest workspaces
 * and retrying, so a big chart payload never silently fails.
 */
function localSave(meta: Omit<WorkspaceMeta, "updatedAt">, state: SavedState) {
    const now = Date.now();
    const record: WorkspaceRecord = { ...meta, updatedAt: now, state };

    let index = readIndex().filter((w) => w.id !== meta.id);
    index.unshift({ ...meta, updatedAt: now });
    index = index.slice(0, MAX_WORKSPACES);

    const persist = (): boolean => {
        try {
            localStorage.setItem(recordKey(meta.id), JSON.stringify(record));
            writeIndex(index);
            return true;
        } catch {
            return false;
        }
    };

    // Drop oldest records until it fits (or we run out).
    while (!persist()) {
        const victim = index.pop();
        if (!victim || victim.id === meta.id) break;
        localStorage.removeItem(recordKey(victim.id));
    }
}

// ── public API (server-first, local fallback) ───────────────────────────────

/**
 * Newest first. Server list merged with any local-only workspaces (e.g. runs
 * saved before server-side persistence existed, or saved while offline).
 */
export async function listWorkspaces(): Promise<WorkspaceMeta[]> {
    let metas: WorkspaceMeta[] = [];
    try {
        metas = (await api.listWorkspaces()).workspaces || [];
    } catch {
        return localList();
    }
    const seen = new Set(metas.map((m) => m.id));
    for (const local of localList()) {
        if (!seen.has(local.id)) metas.push(local);
    }
    return metas.sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function loadWorkspace(id: string): Promise<WorkspaceRecord | null> {
    try {
        return await api.getWorkspace(id);
    } catch {
        return localLoad(id);
    }
}

/** Write-through: server is the source of truth, localStorage the cache. */
export async function saveWorkspace(
    meta: Omit<WorkspaceMeta, "updatedAt">,
    state: SavedState
): Promise<void> {
    localSave(meta, state);
    try {
        await api.saveWorkspace(meta.id, {
            datasetName: meta.datasetName,
            filePath: meta.filePath,
            createdAt: meta.createdAt,
            state,
        });
    } catch {
        // Offline or backend down — the local copy above still has it.
    }
}

export async function deleteWorkspace(id: string): Promise<void> {
    localDelete(id);
    try {
        await api.deleteWorkspace(id);
    } catch {
        // Server copy (if any) will be evicted eventually; local copy is gone.
    }
}
