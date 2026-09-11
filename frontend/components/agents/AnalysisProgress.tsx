"use client";

import { Check, X } from "lucide-react";
import { ANALYSIS_FLOW, metaFor } from "@/lib/agents";
import type { Agent } from "./AgentTimeline";

interface Props {
    agents: Agent[];
    datasetName: string;
}

/**
 * What the Canvas shows while /process is running — a live step tracker
 * plus a focused card for whichever agent is active right now, instead of
 * a bare shimmer with no sense of progress or what's actually happening.
 * Backed by the same SSE agent stream as the conversation pane's timeline.
 */
export function AnalysisProgress({ agents, datasetName }: Props) {
    const list = agents.length > 0 ? agents : ANALYSIS_FLOW.map((id) => ({ id, status: "waiting" as const }));
    const current =
        list.find((a) => a.status === "running") ?? list.find((a) => a.status === "waiting") ?? list[list.length - 1];
    const doneCount = list.filter((a) => a.status === "done").length;
    const meta = metaFor(current.id);
    const CurrentIcon = meta.Icon;

    return (
        <div className="flex flex-col items-center gap-7 py-8">
            {/* Step tracker */}
            <div className="flex items-center">
                {list.map((a, i) => {
                    const m = metaFor(a.id);
                    const StepIcon = m.Icon;
                    const isDone = a.status === "done";
                    const isRunning = a.status === "running";
                    const isError = a.status === "error";
                    const active = isDone || isRunning;
                    return (
                        <div key={a.id} className="flex items-center">
                            <div
                                className={`grid h-10 w-10 place-items-center rounded-full border-2 transition-all duration-300 ${
                                    isRunning ? "animate-pulse" : ""
                                }`}
                                style={{
                                    borderColor: active ? m.color : "var(--border)",
                                    color: active ? m.color : "var(--faint)",
                                    background: isDone ? `${m.color}1a` : "transparent",
                                }}
                            >
                                {isError ? (
                                    <X size={16} className="text-danger" />
                                ) : isDone ? (
                                    <Check size={16} />
                                ) : (
                                    <StepIcon size={16} />
                                )}
                            </div>
                            {i < list.length - 1 && (
                                <div
                                    className="h-0.5 w-6 transition-colors duration-300 sm:w-10"
                                    style={{ background: isDone ? m.color : "var(--border)" }}
                                />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Current stage */}
            <div className="flex max-w-sm flex-col items-center text-center">
                <div
                    className="mb-3 grid h-12 w-12 place-items-center rounded-2xl transition-colors duration-300"
                    style={{ background: `${meta.color}1a`, color: meta.color }}
                >
                    <CurrentIcon size={22} />
                </div>
                <p className="text-sm font-semibold text-fg">{meta.name}</p>
                <p className="mt-1 text-xs text-muted">{meta.description}</p>
                <p className="mt-3 text-[11px] text-faint">
                    Step {Math.min(doneCount + 1, list.length)} of {list.length} — analyzing{" "}
                    <span className="text-fg">{datasetName}</span>
                </p>
            </div>
        </div>
    );
}
