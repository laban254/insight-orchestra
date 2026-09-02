"use client";

import { X, Plus, Trash2, Clock, Table2 } from "lucide-react";
import type { WorkspaceMeta } from "@/lib/workspaces";

function timeAgo(ts: number): string {
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
}

interface Props {
    open: boolean;
    onClose: () => void;
    workspaces: WorkspaceMeta[];
    activeId: string | null;
    onOpen: (id: string) => void;
    onDelete: (id: string) => void;
    onNew: () => void;
}

export function HistoryDrawer({ open, onClose, workspaces, activeId, onOpen, onDelete, onNew }: Props) {
    return (
        <>
            {/* Scrim */}
            <div
                className={`fixed inset-0 z-40 bg-black/40 transition-opacity ${
                    open ? "opacity-100" : "pointer-events-none opacity-0"
                }`}
                onClick={onClose}
            />

            {/* Panel */}
            <aside
                className={`fixed left-0 top-0 z-50 flex h-full w-80 max-w-[85vw] flex-col border-r border-border bg-surface transition-transform duration-300 ${
                    open ? "translate-x-0" : "-translate-x-full"
                }`}
            >
                <div className="flex items-center justify-between border-b border-border px-4 py-3">
                    <h2 className="flex items-center gap-2 text-sm font-semibold text-fg">
                        <Clock size={15} className="text-accent" /> History
                    </h2>
                    <button
                        onClick={onClose}
                        aria-label="Close history"
                        className="grid h-8 w-8 place-items-center rounded-lg text-muted transition-colors hover:text-fg"
                    >
                        <X size={16} aria-hidden="true" />
                    </button>
                </div>

                <div className="p-3">
                    <button
                        onClick={onNew}
                        className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90"
                    >
                        <Plus size={16} /> New analysis
                    </button>
                </div>

                <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-4">
                    {workspaces.length === 0 ? (
                        <p className="px-2 py-8 text-center text-xs text-faint">
                            No saved analyses yet. Your runs will appear here.
                        </p>
                    ) : (
                        workspaces.map((w) => {
                            const active = w.id === activeId;
                            return (
                                <div
                                    key={w.id}
                                    className={`group flex items-center gap-2 rounded-xl border px-3 py-2.5 transition-colors ${
                                        active ? "border-accent/50 bg-accent-soft/30" : "border-transparent hover:bg-surface-2"
                                    }`}
                                >
                                    <button onClick={() => onOpen(w.id)} className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
                                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-accent">
                                            <Table2 size={14} />
                                        </span>
                                        <span className="min-w-0">
                                            <span className="block truncate text-sm font-medium text-fg">{w.datasetName}</span>
                                            <span className="block text-[11px] text-faint">{timeAgo(w.updatedAt)}</span>
                                        </span>
                                    </button>
                                    {/* aria-label names the target: a bare "Delete" repeats
                                        identically down the list and is ambiguous out of
                                        visual context. */}
                                    <button
                                        onClick={() => onDelete(w.id)}
                                        aria-label={`Delete analysis: ${w.datasetName}`}
                                        title="Delete"
                                        className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-faint opacity-0 transition-all hover:text-danger group-hover:opacity-100 focus-visible:opacity-100"
                                    >
                                        <Trash2 size={14} aria-hidden="true" />
                                    </button>
                                </div>
                            );
                        })
                    )}
                </div>
            </aside>
        </>
    );
}
