"use client";

import { useState } from "react";
import { ChevronRight, Check, X, Minus } from "lucide-react";
import { metaFor } from "@/lib/agents";
import type { Agent } from "./AgentTimeline";

/** Collapsible one-line recap of a finished pipeline, attached under an answer. */
export function PipelineSummary({ agents }: { agents: Agent[] }) {
    const [open, setOpen] = useState(false);

    const acted = agents.filter((a) => a.status === "done" || a.status === "error");
    if (acted.length === 0) return null;

    const totalMs = agents.reduce((s, a) => s + (a.duration ?? 0), 0);
    const hasError = agents.some((a) => a.status === "error");
    const time = totalMs > 0 ? (totalMs < 1000 ? `${totalMs}ms` : `${(totalMs / 1000).toFixed(1)}s`) : "";

    return (
        <div className="text-xs">
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-1.5 font-medium text-muted transition-colors hover:text-fg"
            >
                <ChevronRight
                    size={13}
                    className={`transition-transform ${open ? "rotate-90" : ""}`}
                />
                <span className="flex items-center gap-1">
                    {agents.map((a) => {
                        const meta = metaFor(a.id);
                        const Icon = meta.Icon;
                        return (
                            <Icon
                                key={a.id}
                                size={12}
                                style={{
                                    color:
                                        a.status === "done"
                                            ? meta.color
                                            : a.status === "error"
                                              ? "var(--color-danger)"
                                              : "var(--color-faint)",
                                    opacity: a.status === "skipped" || a.status === "waiting" ? 0.4 : 1,
                                }}
                            />
                        );
                    })}
                </span>
                <span className={hasError ? "text-danger" : ""}>
                    {acted.length} agent{acted.length !== 1 ? "s" : ""}
                    {time && <span className="text-faint"> · {time}</span>}
                </span>
            </button>

            {open && (
                <ul className="ml-2 mt-2 flex flex-col gap-1.5 border-l border-border pl-3">
                    {agents.map((a) => {
                        const meta = metaFor(a.id);
                        return (
                            <li key={a.id} className="flex items-start gap-2">
                                <span className="mt-0.5">
                                    {a.status === "done" ? (
                                        <Check size={12} style={{ color: meta.color }} />
                                    ) : a.status === "error" ? (
                                        <X size={12} className="text-danger" />
                                    ) : (
                                        <Minus size={12} className="text-faint" />
                                    )}
                                </span>
                                <div className="min-w-0">
                                    <span className="font-medium text-muted">{meta.name}</span>
                                    {a.output && <p className="mt-0.5 text-faint">{a.output}</p>}
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
