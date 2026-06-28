"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, CornerDownLeft } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface Command {
    id: string;
    label: string;
    hint?: string;
    group?: string;
    icon: LucideIcon;
    run: () => void;
}

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    commands: Command[];
}

export function CommandPalette({ open, onOpenChange, commands }: Props) {
    const [query, setQuery] = useState("");
    const [active, setActive] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);

    // Global Cmd/Ctrl+K toggles the palette.
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                onOpenChange(!open);
            }
            if (e.key === "Escape") onOpenChange(false);
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onOpenChange]);

    useEffect(() => {
        if (open) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setQuery("");
            setActive(0);
            setTimeout(() => inputRef.current?.focus(), 30);
        }
    }, [open]);

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        return q ? commands.filter((c) => c.label.toLowerCase().includes(q) || c.group?.toLowerCase().includes(q)) : commands;
    }, [query, commands]);

    if (!open) return null;

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
            if (cmd) {
                onOpenChange(false);
                cmd.run();
            }
        }
    };

    return (
        <div className="fixed inset-0 z-[70] flex items-start justify-center bg-black/50 p-4 pt-[12vh]" onClick={() => onOpenChange(false)}>
            <div
                className="animate-rise w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--shadow)]"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center gap-2.5 border-b border-border px-4">
                    <Search size={16} className="text-faint" />
                    <input
                        ref={inputRef}
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setActive(0);
                        }}
                        onKeyDown={onKeyDown}
                        placeholder="Type a command or search…"
                        className="flex-1 bg-transparent py-3.5 text-sm text-fg outline-none placeholder:text-faint"
                    />
                    <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-faint">ESC</kbd>
                </div>

                <div className="max-h-80 overflow-y-auto p-2">
                    {filtered.length === 0 ? (
                        <p className="px-3 py-6 text-center text-sm text-faint">No matching commands</p>
                    ) : (
                        filtered.map((c, i) => {
                            const Icon = c.icon;
                            return (
                                <button
                                    key={c.id}
                                    onMouseEnter={() => setActive(i)}
                                    onClick={() => {
                                        onOpenChange(false);
                                        c.run();
                                    }}
                                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                                        i === active ? "bg-surface-2 text-fg" : "text-muted"
                                    }`}
                                >
                                    <Icon size={15} className="shrink-0 text-accent" />
                                    <span className="flex-1">{c.label}</span>
                                    {c.hint && <span className="text-[11px] text-faint">{c.hint}</span>}
                                    {i === active && <CornerDownLeft size={13} className="text-faint" />}
                                </button>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
