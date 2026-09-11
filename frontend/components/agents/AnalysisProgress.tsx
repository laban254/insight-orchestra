"use client";

import { useEffect, useState } from "react";
import { ANALYSIS_FLOW, metaFor } from "@/lib/agents";
import type { Agent } from "./AgentTimeline";

interface Props {
    agents: Agent[];
    datasetName: string;
}

// Present-continuous, plain-English captions — the same idea as Perplexity's
// "Searching… / Reading sources… / Writing answer": one line that changes as
// real work happens, not a formal agent name. That's what actually reads as
// progress, per how every mainstream AI product handles a 10s+ generation.
const CAPTION: Record<string, string> = {
    janitor: "Cleaning up duplicates and gaps",
    hypothesis: "Looking for patterns worth testing",
    debate: "Weighing which findings matter most",
    viz: "Building the charts",
    narrator: "Writing up the findings",
};

function useElapsedSeconds() {
    const [seconds, setSeconds] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setSeconds((s) => s + 1), 1000);
        return () => clearInterval(id);
    }, []);
    return seconds;
}

/**
 * What the Canvas shows while /process is running. Research on waits past
 * ~10s (this pipeline runs a real LLM through 5 stages, often 30-90s+) is
 * consistent: a static skeleton or a step tracker with no forward motion
 * reads as stuck. What people actually find pleasant is a simple loader
 * paired with real, plain-English status text that changes as work
 * happens — the same idea as Perplexity/ChatGPT's staged captions — plus a
 * ticking clock so the wait never looks frozen.
 */
export function AnalysisProgress({ agents, datasetName }: Props) {
    const list = agents.length > 0 ? agents : ANALYSIS_FLOW.map((id) => ({ id, status: "waiting" as const }));
    const current =
        list.find((a) => a.status === "running") ?? list.find((a) => a.status === "waiting") ?? list[list.length - 1];
    const meta = metaFor(current.id);
    const caption = CAPTION[current.id] ?? "Working on it";
    const seconds = useElapsedSeconds();

    return (
        <div className="flex flex-col items-center gap-5 py-16">
            {/* Breathing loader — the ring's own motion is the "still alive" signal */}
            <div className="relative h-14 w-14">
                <div
                    className="animate-pulse-ring absolute inset-0 rounded-full"
                    style={{ background: meta.color }}
                />
                <div
                    className="absolute inset-[10px] rounded-full transition-colors duration-500"
                    style={{ background: meta.color }}
                />
            </div>

            {/* Real, changing status line */}
            <div key={current.id} className="animate-fade flex items-center gap-2">
                <span className="text-sm font-medium text-fg">{caption}…</span>
            </div>

            <p className="font-mono text-xs text-faint">
                {seconds}s · analyzing {datasetName}
            </p>
        </div>
    );
}
