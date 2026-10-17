"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, CornerDownLeft } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCloseMenus } from "@/lib/menus";
import { useDialogA11y } from "@/lib/useDialogA11y";

export interface Command {
    id: string;
    label: string;
    hint?: string;
    group?: string;
    icon: LucideIcon;
    run: () => void;
}

const RECENT_KEY = "io-cmd-recent";

/** Friendly headings for the internal group ids. */
const GROUP_LABELS: Record<string, string> = {
    actions: "Actions",
    datasets: "Datasets",
};

function groupLabel(group: string): string {
    return GROUP_LABELS[group] ?? group.charAt(0).toUpperCase() + group.slice(1);
}

/**
 * Subsequence match with a contiguity bonus: "expt" finds "Export report",
 * and a run of adjacent characters scores higher than scattered hits. Returns
 * null when the query isn't a subsequence at all.
 */
function fuzzyScore(text: string, query: string): number | null {
    const t = text.toLowerCase();
    let qi = 0;
    let score = 0;
    let streak = 0;
    for (let i = 0; i < t.length && qi < query.length; i++) {
        if (t[i] === query[qi]) {
            score += 1 + streak;
            streak += 1;
            qi += 1;
        } else {
            streak = 0;
        }
    }
    return qi === query.length ? score : null;
}

function readRecent(): string[] {
    try {
        return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    } catch {
        return [];
    }
}

function rememberRecent(id: string) {
    try {
        const next = [id, ...readRecent().filter((x) => x !== id)].slice(0, 5);
        localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
        /* storage disabled — recents are a nicety, not a feature */
    }
}

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    commands: Command[];
}

export function CommandPalette({ open, onOpenChange, commands }: Props) {
    const [query, setQuery] = useState("");
    const [active, setActive] = useState(0);
    const closeMenus = useCloseMenus();
    const panelRef = useDialogA11y<HTMLDivElement>(open);

    // A full-screen overlay takes over — no header dropdown should linger under it.
    useEffect(() => {
        if (open) closeMenus();
    }, [open, closeMenus]);

    // Global Cmd/Ctrl+K toggles the palette; Escape closes it.
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                onOpenChange(!open);
            } else if (e.key === "Escape" && open) {
                onOpenChange(false);
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onOpenChange]);

    useEffect(() => {
        if (open) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setQuery("");
            setActive(0);
        }
    }, [open]);

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) {
            // No query: surface recently-used commands first, then the rest.
            const recent = readRecent();
            return [...commands].sort((a, b) => {
                const ai = recent.indexOf(a.id);
                const bi = recent.indexOf(b.id);
                if (ai === -1 && bi === -1) return 0;
                if (ai === -1) return 1;
                if (bi === -1) return -1;
                return ai - bi;
            });
        }
        return commands
            .map((c) => ({ c, s: fuzzyScore(`${c.label} ${c.group ?? ""}`, q) }))
            .filter((x): x is { c: Command; s: number } => x.s !== null)
            .sort((a, b) => b.s - a.s)
            .map((x) => x.c);
    }, [query, commands]);

    if (!open) return null;

    const run = (cmd: Command) => {
        rememberRecent(cmd.id);
        onOpenChange(false);
        cmd.run();
    };

    const onKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, filtered.length - 1));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            const cmd = filtered[active];
            if (cmd) run(cmd);
        }
    };

    // Preserve `filtered` order while inserting a heading per group.
    const groups: { name: string; items: Command[] }[] = [];
    filtered.forEach((c) => {
        const name = c.group ?? "actions";
        const last = groups[groups.length - 1];
        if (last && last.name === name) last.items.push(c);
        else groups.push({ name, items: [c] });
    });

    const activeId = filtered[active]?.id;

    return (
        <div
            className="fixed inset-0 z-[70] flex items-start justify-center bg-black/50 p-4 pt-[12vh]"
            onClick={() => onOpenChange(false)}
        >
            <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-label="Command palette"
                tabIndex={-1}
                className="animate-rise w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--shadow)] outline-none"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center gap-2.5 border-b border-border px-4">
                    <Search size={16} className="text-faint" aria-hidden="true" />
                    <input
                        data-autofocus
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setActive(0);
                        }}
                        onKeyDown={onKeyDown}
                        placeholder="Type a command or search…"
                        aria-label="Search commands"
                        aria-controls="command-list"
                        aria-activedescendant={activeId ? `cmd-opt-${activeId}` : undefined}
                        className="flex-1 bg-transparent py-3.5 text-sm text-fg outline-none placeholder:text-faint"
                    />
                    <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-faint">ESC</kbd>
                </div>

                <div id="command-list" className="max-h-80 overflow-y-auto p-2">
                    {filtered.length === 0 ? (
                        <p className="px-3 py-6 text-center text-sm text-faint">No matching commands</p>
                    ) : (
                        groups.map((group) => (
                            <div key={group.name} className="mb-1 last:mb-0">
                                <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-faint">
                                    {groupLabel(group.name)}
                                </p>
                                {group.items.map((c) => {
                                    const Icon = c.icon;
                                    const i = filtered.indexOf(c);
                                    const isActive = i === active;
                                    return (
                                        <button
                                            key={c.id}
                                            id={`cmd-opt-${c.id}`}
                                            role="option"
                                            aria-selected={isActive}
                                            onMouseEnter={() => setActive(i)}
                                            onClick={() => run(c)}
                                            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                                                isActive ? "bg-surface-2 text-fg" : "text-muted"
                                            }`}
                                        >
                                            <Icon size={15} className="shrink-0 text-accent" aria-hidden="true" />
                                            <span className="flex-1">{c.label}</span>
                                            {c.hint && <span className="text-[11px] text-faint">{c.hint}</span>}
                                            {isActive && (
                                                <CornerDownLeft size={13} className="text-faint" aria-hidden="true" />
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
