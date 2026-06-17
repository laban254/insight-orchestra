"use client";

import { useEffect, useRef, useState } from "react";
import { Check, X, Loader2, Minus } from "lucide-react";
import { metaFor } from "@/lib/agents";

export type AgentStatus = "waiting" | "running" | "done" | "error" | "skipped";

export interface Agent {
    id: string;
    status: AgentStatus;
    output?: string;
    duration?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
    sessionId: string;
    /** Ordered agent ids for this run. */
    flow: readonly string[];
    /** Bumping this (re)starts a fresh stream. `null` = idle. */
    runId: number | null;
    /** Caller flips true once the underlying request resolves. */
    finished: boolean;
    onAgentsChange?: (agents: Agent[]) => void;
}

/**
 * One unified, SSE-driven view of the agent pipeline. Replaces the old
 * AgentPipeline + PipelineBlock split with a single visual language.
 */
export function AgentTimeline({ sessionId, flow, runId, finished, onAgentsChange }: Props) {
    const [agents, setAgents] = useState<Agent[]>(() =>
        flow.map((id) => ({ id, status: "waiting" as AgentStatus }))
    );
    const sourceRef = useRef<EventSource | null>(null);
    const onChangeRef = useRef(onAgentsChange);
    onChangeRef.current = onAgentsChange;

    // (Re)open the stream whenever a new run starts.
    useEffect(() => {
        if (runId === null) return;
        setAgents(flow.map((id) => ({ id, status: "waiting" as AgentStatus })));

        const source = new EventSource(`${API_BASE}/agents/stream/${sessionId}`);
        sourceRef.current = source;

        source.onmessage = (e) => {
            try {
                const u = JSON.parse(e.data);
                setAgents((prev) => {
                    const next = prev.map((a) =>
                        a.id === u.agent_id
                            ? { ...a, status: u.status, output: u.output, duration: u.duration }
                            : a
                    );
                    onChangeRef.current?.(next);
                    return next;
                });
            } catch {
                /* ignore malformed frames */
            }
        };

        source.onerror = () => {
            source.close();
            setAgents((prev) => prev.map((a) => (a.status === "running" ? { ...a, status: "done" } : a)));
        };

        return () => {
            source.close();
            sourceRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [runId, sessionId]);

    // Once the request resolves, settle any unreached agents.
    const display: Agent[] = finished
        ? agents.map((a) => {
              if (a.status === "running") return { ...a, status: "done" as AgentStatus };
              if (a.status === "waiting") {
                  return a.id === "viz"
                      ? { ...a, status: "skipped" as AgentStatus, output: "No chart needed for this query." }
                      : { ...a, status: "skipped" as AgentStatus };
              }
              return a;
          })
        : agents;

    return (
        <ol className="relative flex flex-col gap-1">
            {display.map((agent, i) => {
                const meta = metaFor(agent.id);
                const Icon = meta.Icon;
                const isLast = i === display.length - 1;
                const active = agent.status === "running";
                const muted = agent.status === "waiting" || agent.status === "skipped";

                return (
                    <li key={agent.id} className="relative flex gap-3 pb-1">
                        {/* Connector */}
                        {!isLast && (
                            <span
                                className="absolute left-[17px] top-9 h-[calc(100%-1.25rem)] w-px"
                                style={{
                                    background:
                                        agent.status === "done"
                                            ? `${meta.color}55`
                                            : "var(--color-border)",
                                }}
                            />
                        )}

                        {/* Node */}
                        <span
                            className={`relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition-all duration-300 ${
                                muted ? "opacity-50" : ""
                            }`}
                            style={{
                                borderColor:
                                    agent.status === "error"
                                        ? "var(--color-danger)"
                                        : active || agent.status === "done"
                                          ? meta.color
                                          : "var(--color-border)",
                                background: active
                                    ? `${meta.color}1a`
                                    : "var(--color-surface)",
                                boxShadow: active ? `0 0 16px -4px ${meta.color}` : undefined,
                                color: agent.status === "error" ? "var(--color-danger)" : meta.color,
                            }}
                        >
                            {agent.status === "done" ? (
                                <Check size={16} style={{ color: meta.color }} />
                            ) : agent.status === "error" ? (
                                <X size={16} />
                            ) : agent.status === "skipped" ? (
                                <Minus size={15} className="text-faint" />
                            ) : active ? (
                                <Loader2 size={16} className="animate-spin" style={{ color: meta.color }} />
                            ) : (
                                <Icon size={16} />
                            )}
                        </span>

                        {/* Body */}
                        <div className={`min-w-0 flex-1 pt-1 ${muted ? "opacity-60" : ""}`}>
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-semibold text-fg">{meta.name}</span>
                                {active && (
                                    <span
                                        className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                                        style={{ background: `${meta.color}1a`, color: meta.color }}
                                    >
                                        working…
                                    </span>
                                )}
                                {agent.status === "done" && agent.duration != null && (
                                    <span className="font-mono text-[11px] text-faint">
                                        {agent.duration < 1000
                                            ? `${agent.duration}ms`
                                            : `${(agent.duration / 1000).toFixed(1)}s`}
                                    </span>
                                )}
                                {agent.status === "skipped" && (
                                    <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] text-faint">
                                        skipped
                                    </span>
                                )}
                            </div>
                            <p className="mt-0.5 text-xs text-faint">{meta.description}</p>
                            {agent.output && (agent.status === "done" || agent.status === "error") && (
                                <p
                                    className={`mt-1.5 rounded-lg border px-3 py-2 text-xs leading-relaxed ${
                                        agent.status === "error"
                                            ? "border-danger/30 bg-danger/10 text-danger"
                                            : "border-border-soft bg-surface-2 text-muted"
                                    }`}
                                >
                                    {agent.output}
                                </p>
                            )}
                        </div>
                    </li>
                );
            })}
        </ol>
    );
}
