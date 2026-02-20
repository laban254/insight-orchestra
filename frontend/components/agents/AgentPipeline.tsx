"use client";

import { useState, useEffect } from "react";

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

const AGENTS: Agent[] = [
    {
        id: "janitor", name: "Data Janitor", emoji: "🧹",
        description: "Cleaning duplicates, imputing missing values"
    },
    {
        id: "hypothesis", name: "Hypothesis Bot", emoji: "🔬",
        description: "Generating testable hypotheses from your data"
    },
    {
        id: "debate", name: "Debate Manager", emoji: "⚖️",
        description: "Scoring hypotheses by confidence & business value"
    },
    {
        id: "viz", name: "Viz Whiz", emoji: "📊",
        description: "Auto-generating Plotly charts"
    },
].map(a => ({ ...a, status: "waiting" }));

export function AgentPipeline({ sessionId }: { sessionId: string }) {
    const [agents, setAgents] = useState<Agent[]>(AGENTS);

    // Poll for agent status updates via SSE or polling
    useEffect(() => {
        // Connect to the actual SSE endpoint if sessionId is present
        if (!sessionId) return;

        // As a demonstration for SSE integration.
        // Replace URL below with the correct endpoint that streams back standard SSE messages.
        const source = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/agents/stream/${sessionId}`);

        source.onmessage = (e) => {
            try {
                const update = JSON.parse(e.data);
                setAgents(prev => prev.map(a =>
                    a.id === update.agent_id ? { ...a, ...update } : a
                ));
            } catch (err) {
                console.error("Failed to parse agent update", err);
            }
        };

        source.onerror = () => {
            source.close();
        };

        return () => source.close();
    }, [sessionId]);

    return (
        <div className="flex flex-col gap-3 p-4 bg-white rounded-xl shadow-sm border border-gray-100 my-4">
            <h3 className="text-sm font-semibold text-gray-800 border-b pb-2 mb-2">Analysis Pipeline</h3>
            {agents.map((agent, i) => (
                <div key={agent.id} className="flex items-start gap-4 relative">
                    {/* Connector line between agents */}
                    {i < agents.length - 1 && (
                        <div className="absolute left-[19px] top-10 w-0.5 h-6 bg-gray-200" />
                    )}

                    {/* Status icon */}
                    <div className={`
            w-10 h-10 rounded-full flex items-center justify-center text-lg z-10
            flex-shrink-0 border-2 transition-all duration-300 bg-white
            ${agent.status === "running" ? "border-blue-500 bg-blue-50 animate-pulse text-blue-600" : ""}
            ${agent.status === "done" ? "border-green-500 bg-green-50 text-green-600" : ""}
            ${agent.status === "error" ? "border-red-500 bg-red-50 text-red-600" : ""}
            ${agent.status === "waiting" ? "border-gray-200 text-gray-400 grayscale" : ""}
          `}>
                        {agent.emoji}
                    </div>

                    {/* Agent info */}
                    <div className={`flex-1 min-w-0 transition-opacity duration-300 ${agent.status === "waiting" ? "opacity-50" : "opacity-100"}`}>
                        <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-gray-800">{agent.name}</span>
                            {agent.status === "running" && (
                                <span className="text-xs font-medium text-blue-600 animate-pulse bg-blue-50 px-2 py-0.5 rounded-full">
                                    Processing...
                                </span>
                            )}
                            {agent.status === "done" && agent.duration && (
                                <span className="text-xs text-gray-400 font-mono">
                                    {agent.duration}ms
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{agent.description}</p>
                        {agent.output && agent.status === "done" && (
                            <div className="mt-2 text-xs bg-gray-50 rounded-md p-3 border border-gray-100 text-gray-700 leading-relaxed shadow-sm">
                                {agent.output}
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
