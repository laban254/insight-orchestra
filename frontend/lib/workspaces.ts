/**
 * Client-side workspace persistence (localStorage).
 *
 * Each analysis is saved as a "workspace" so users get history and can reopen
 * past runs across refreshes without re-running the pipeline. A lightweight
 * index powers the history list; full state lives in per-workspace keys.
 */

import type { ProcessResponse } from "./types";
import type { ChatMessage } from "@/components/chat/MessageBubble";
import type { QueryResult } from "@/components/workspace/CanvasPane";

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

/** Newest first. */
export function listWorkspaces(): WorkspaceMeta[] {
    return readIndex().sort((a, b) => b.updatedAt - a.updatedAt);
}

export function loadWorkspace(id: string): WorkspaceRecord | null {
    try {
        const raw = localStorage.getItem(recordKey(id));
        return raw ? (JSON.parse(raw) as WorkspaceRecord) : null;
    } catch {
        return null;
    }
}

export function deleteWorkspace(id: string) {
    localStorage.removeItem(recordKey(id));
    writeIndex(readIndex().filter((w) => w.id !== id));
}

/**
 * Upsert a workspace. Handles localStorage quota by evicting the oldest
 * workspaces and retrying, so a big chart payload never silently fails.
 */
export function saveWorkspace(meta: Omit<WorkspaceMeta, "updatedAt">, state: SavedState) {
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
