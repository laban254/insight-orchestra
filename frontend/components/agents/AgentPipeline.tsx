"use client";

import { useState, useEffect, useRef } from "react";

type AgentStatus = "waiting" | "running" | "done" | "error";

interface Agent {
    id: string;
    name: string;
    emoji: string;
    description: string;
    status: AgentStatus;
    output?: string;
    duration?: number;
}

const INITIAL_AGENTS: Agent[] = [
    { id: "janitor",    name: "Data Janitor",    emoji: "🧹", description: "Cleaning duplicates, imputing missing values" },
    { id: "hypothesis", name: "Hypothesis Bot",  emoji: "🔬", description: "Generating testable hypotheses from your data" },
    { id: "debate",     name: "Debate Manager",  emoji: "⚖️", description: "Scoring hypotheses by confidence & business value" },
    { id: "viz",        name: "Viz Whiz",        emoji: "📊", description: "Auto-generating Plotly charts" },
].map(a => ({ ...a, status: "waiting" as AgentStatus }));

interface AgentPipelineProps {
    sessionId: string;
    /** When true, stop listening and freeze the UI in its final state */
    isDone?: boolean;
}

export function AgentPipeline({ sessionId, isDone }: AgentPipelineProps) {
    const [agents, setAgents] = useState<Agent[]>(INITIAL_AGENTS);
    const [complete, setComplete] = useState(false);
    const sourceRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (!sessionId || isDone) return;

        // Reset to initial state when a new query starts
        setAgents(INITIAL_AGENTS);
        setComplete(false);

        const source = new EventSource(
            `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/agents/stream/${sessionId}`
        );
        sourceRef.current = source;

        source.onmessage = (e) => {
            try {
                const update = JSON.parse(e.data);
                setAgents(prev =>
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
            // Mark any still-running agents as done on disconnect
            setAgents(prev => prev.map(a => a.status === "running" ? { ...a, status: "done" } : a));
        };

        return () => {
            source.close();
            sourceRef.current = null;
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    // When parent signals isDone, lock the pipeline
    useEffect(() => {
        if (isDone) {
            sourceRef.current?.close();
            // Promote any lingering "running" to "done"
            setAgents(prev => prev.map(a => a.status === "running" ? { ...a, status: "done" } : a));
            setComplete(true);
        }
    }, [isDone]);

    const anyActive = agents.some(a => a.status === "running" || a.status === "done");
    if (!anyActive && !isDone) return null; // Hide until first event arrives

    return (
        <div className="flex flex-col gap-3 p-4 bg-white rounded-xl shadow-sm border border-gray-100 my-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider border-b pb-2 mb-1">
                Analysis Pipeline
            </h3>

            {agents.map((agent, i) => (
                <div key={agent.id} className="flex items-start gap-3 relative">
                    {/* Connector line */}
                    {i < agents.length - 1 && (
                        <div className="absolute left-[17px] top-9 w-0.5 h-5 bg-gray-100" />
                    )}

                    {/* Status icon */}
                    <div className={`
                        w-9 h-9 rounded-full flex items-center justify-center text-base z-10 flex-shrink-0
                        border-2 transition-all duration-300 bg-white
                        ${agent.status === "running" ? "border-blue-400 bg-blue-50 animate-pulse" : ""}
                        ${agent.status === "done"    ? "border-green-400 bg-green-50" : ""}
                        ${agent.status === "error"   ? "border-red-400 bg-red-50" : ""}
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
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">{agent.description}</p>

                        {agent.output && agent.status === "done" && (
                            <div className="mt-1.5 text-xs bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 text-gray-600 leading-relaxed">
                                {agent.output}
                            </div>
                        )}
                    </div>
                </div>
            ))}

            {complete && (
                <div className="mt-1 pt-2 border-t border-gray-100 flex items-center gap-1.5 text-xs text-green-600 font-medium">
                    <span>✓</span>
                    <span>Analysis complete</span>
                </div>
            )}
        </div>
    );
}
