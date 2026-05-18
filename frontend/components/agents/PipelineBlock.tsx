"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { Agent } from "./AgentPipeline";

const STATUS_COLORS: Record<string, string> = {
    done:    "text-green-500",
    error:   "text-red-500",
    skipped: "text-gray-300",
    running: "text-blue-400",
    waiting: "text-gray-300",
};

const STATUS_ICONS: Record<string, string> = {
    done:    "✓",
    error:   "✗",
    skipped: "–",
    running: "◌",
    waiting: "◌",
};

interface PipelineBlockProps {
    agents: Agent[];
    isRunning?: boolean;
}

export function PipelineBlock({ agents, isRunning = false }: PipelineBlockProps) {
    const [open, setOpen] = useState(false);

    const anyActive = agents.some(a => a.status !== "waiting");
    if (!anyActive && !isRunning) return null;

    const doneCount  = agents.filter(a => a.status === "done" || a.status === "error").length;
    const totalMs    = agents.reduce((sum, a) => sum + (a.duration ?? 0), 0);
    const hasError   = agents.some(a => a.status === "error");

    const labelColor = isRunning
        ? "text-gray-400"
        : hasError
            ? "text-red-500"
            : "text-purple-600";

    const label = isRunning
        ? "Running…"
        : `${doneCount} agent${doneCount !== 1 ? "s" : ""}`;

    const timeLabel = !isRunning && totalMs > 0
        ? ` · ${totalMs < 1000 ? `${totalMs}ms` : `${(totalMs / 1000).toFixed(1)}s`}`
        : "";

    return (
        <div className="mb-2">
            <button
                onClick={() => setOpen(o => !o)}
                className={`flex items-center gap-1.5 text-xs font-medium ${labelColor} hover:opacity-70 transition-opacity`}
            >
                {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                {isRunning && <Loader2 size={11} className="animate-spin" />}
                <span>
                    {label}
                    {timeLabel && <span className="text-gray-400 font-normal">{timeLabel}</span>}
                </span>
            </button>

            {open && (
                <div className="mt-2 ml-0.5 flex flex-col gap-2 border-l-2 border-gray-100 pl-3">
                    {agents.map(agent => (
                        <div
                            key={agent.id}
                            className={`transition-opacity ${agent.status === "waiting" || agent.status === "skipped" ? "opacity-40" : ""}`}
                        >
                            <div className="flex items-center gap-2">
                                <span className={`text-xs font-bold ${STATUS_COLORS[agent.status] ?? "text-gray-400"}`}>
                                    {STATUS_ICONS[agent.status]}
                                </span>
                                <span className="text-xs font-medium text-gray-700">
                                    {agent.emoji} {agent.name}
                                </span>
                                {agent.status === "done" && agent.duration != null && (
                                    <span className="text-xs text-gray-400 font-mono">{agent.duration}ms</span>
                                )}
                                {agent.status === "running" && (
                                    <span className="text-xs text-blue-400 animate-pulse">processing…</span>
                                )}
                                {agent.status === "skipped" && (
                                    <span className="text-xs text-gray-400">skipped</span>
                                )}
                                {agent.status === "error" && (
                                    <span className="text-xs text-red-400">error</span>
                                )}
                            </div>
                            {agent.output && (agent.status === "done" || agent.status === "error") && (
                                <p className="text-xs text-gray-400 mt-0.5 pl-4 leading-relaxed">{agent.output}</p>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
