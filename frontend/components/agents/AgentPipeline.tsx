"use client";

import { useState, useEffect, useRef } from "react";

export type AgentStatus = "waiting" | "running" | "done" | "error" | "skipped";
type PipelineMode = "analysis" | "nlq";

export interface Agent {
    id: string;
    name: string;
    emoji: string;
    description: string;
    status: AgentStatus;
    output?: string;
    duration?: number;
}

const ANALYSIS_AGENTS: Omit<Agent, "status">[] = [
    { id: "janitor", name: "Data Janitor", emoji: "🧹", description: "Cleaning duplicates, imputing missing values" },
    { id: "hypothesis", name: "Hypothesis Bot", emoji: "🔬", description: "Generating testable hypotheses from your data" },
    { id: "debate", name: "Debate Manager", emoji: "⚖️", description: "Scoring hypotheses by confidence & business value" },
    { id: "viz", name: "Viz Whiz", emoji: "📊", description: "Auto-generating Plotly charts" },
];

const NLQ_AGENTS: Omit<Agent, "status">[] = [
    { id: "janitor", name: "Data Janitor", emoji: "🧹", description: "Cleaning duplicates, imputing missing values" },
    { id: "nlq", name: "Query Agent", emoji: "🤖", description: "Generating and executing analysis code" },
    { id: "viz", name: "Viz Whiz", emoji: "📊", description: "Generating chart if requested" },
];

const getInitialAgents = (mode: PipelineMode): Agent[] => {
    const base = mode === "nlq" ? NLQ_AGENTS : ANALYSIS_AGENTS;
    return base.map((a) => ({ ...a, status: "waiting" as AgentStatus }));
};

interface AgentPipelineProps {
    sessionId: string;
    isDone?: boolean;
    mode?: PipelineMode;
    variant?: "default" | "sidebar";
    onAgentsChange?: (agents: Agent[]) => void;
}

export function AgentPipeline({ sessionId, isDone, mode = "analysis", variant = "default", onAgentsChange }: AgentPipelineProps) {
    const [agents, setAgents] = useState<Agent[]>(getInitialAgents(mode));
    const sourceRef = useRef<EventSource | null>(null);

    const updateAgents = (updater: (prev: Agent[]) => Agent[]) => {
        setAgents(prev => {
            const next = updater(prev);
            onAgentsChange?.(next);
            return next;
        });
    };

    useEffect(() => {
        if (!sessionId || isDone) return;

        const source = new EventSource(
            `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/agents/stream/${sessionId}`
        );
        sourceRef.current = source;

        source.onmessage = (e) => {
            try {
                const update = JSON.parse(e.data);
                updateAgents(prev =>
                    prev.map(a =>
                        a.id === update.agent_id
                            ? { ...a, status: update.status, output: update.output, duration: update.duration }
                            : a
                    )
                );
            } catch (err) {
                console.error("Failed to parse agent update", err);
            }
        };

        source.onerror = () => {
            source.close();
            updateAgents(prev => prev.map(a => a.status === "running" ? { ...a, status: "done" } : a));
        };

        return () => {
            source.close();
            sourceRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, mode, isDone]);

    useEffect(() => {
        if (isDone) {
            sourceRef.current?.close();
        }
    }, [isDone]);

    const displayAgents = isDone
        ? agents.map((a) => {
              if (a.status === "running") return { ...a, status: "done" as AgentStatus };
              if (a.status === "waiting") {
                  if (a.id === "viz") {
                      return {
                          ...a,
                          status: "skipped" as AgentStatus,
                          output: "No chart requested for this query.",
                      };
                  }
                  return { ...a, status: "skipped" as AgentStatus };
              }
              return a;
          })
        : agents;

    const anyActive = displayAgents.some(a => a.status !== "waiting");
    if (!anyActive && !isDone) return null;

    const isSidebar = variant === "sidebar";

    const content = (
        <>
            {displayAgents.map((agent, i) => (
                <div key={agent.id} className="flex items-start gap-3 relative">
                    {/* Connector line */}
                    {i < displayAgents.length - 1 && (
                        <div className="absolute left-[17px] top-9 w-0.5 h-5 bg-gray-100" />
                    )}

                    {/* Status icon */}
                    <div className={`
                        w-9 h-9 rounded-full flex items-center justify-center text-base z-10 flex-shrink-0
                        border-2 transition-all duration-300 bg-white
                        ${agent.status === "running" ? "border-blue-400 bg-blue-50 animate-pulse" : ""}
                        ${agent.status === "done"    ? "border-green-400 bg-green-50" : ""}
                        ${agent.status === "error"   ? "border-red-400 bg-red-50" : ""}
                        ${agent.status === "skipped" ? "border-gray-200 bg-gray-50" : ""}
                        ${agent.status === "waiting" ? "border-gray-100 opacity-40" : ""}
                    `}>
                        {agent.emoji}
                    </div>

                    {/* Info */}
                    <div className={`flex-1 min-w-0 transition-opacity duration-300 ${agent.status === "waiting" ? "opacity-40" : "opacity-100"}`}>
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-sm text-gray-800">{agent.name}</span>

                            {agent.status === "running" && (
                                <span className="text-xs font-medium text-blue-600 animate-pulse bg-blue-50 px-2 py-0.5 rounded-full">
                                    Processing…
                                </span>
                            )}
                            {agent.status === "done" && agent.duration != null && (
                                <span className="text-xs text-gray-400 font-mono">{agent.duration}ms</span>
                            )}
                            {agent.status === "skipped" && (
                                <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                                    Skipped
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">{agent.description}</p>

                        {agent.output && agent.status === "done" && (
                            <div className="mt-1.5 text-xs bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 text-gray-600 leading-relaxed">
                                {agent.output}
                            </div>
                        )}
                        {agent.output && agent.status === "error" && (
                            <div className="mt-1.5 text-xs bg-red-50 rounded-lg px-3 py-2 border border-red-100 text-red-600 leading-relaxed">
                                {agent.output}
                            </div>
                        )}
                    </div>
                </div>
            ))}

            {isDone && (
                <div className={`pt-2 border-t border-gray-100 flex items-center gap-1.5 text-xs text-green-600 font-medium ${isSidebar ? "mt-2" : "mt-1"}`}>
                    <span>✓</span>
                    <span>{mode === "nlq" ? "Query complete" : "Analysis complete"}</span>
                </div>
            )}
        </>
    );

    if (isSidebar) {
        return <div className="flex flex-col gap-4">{content}</div>;
    }

    return (
        <div className="flex flex-col gap-3 p-4 bg-white rounded-xl shadow-sm border border-gray-100 my-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider border-b pb-2 mb-1">
                {mode === "nlq" ? "Query Pipeline" : "Analysis Pipeline"}
            </h3>
            {content}
        </div>
    );
}
