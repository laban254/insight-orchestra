import {
    Sparkles,
    FlaskConical,
    Scale,
    BarChart3,
    Bot,
    type LucideIcon,
} from "lucide-react";

export interface AgentMeta {
    id: string;
    name: string;
    description: string;
    Icon: LucideIcon;
    /** Accent hue (hex) used for icon, ring and progress tint. */
    color: string;
}

export const AGENT_META: Record<string, AgentMeta> = {
    janitor: {
        id: "janitor",
        name: "Data Janitor",
        description: "Cleans duplicates and imputes missing values",
        Icon: Sparkles,
        color: "#22d3ee", // cyan
    },
    hypothesis: {
        id: "hypothesis",
        name: "Hypothesis Bot",
        description: "Generates testable hypotheses from your data",
        Icon: FlaskConical,
        color: "#a78bfa", // violet
    },
    debate: {
        id: "debate",
        name: "Debate Manager",
        description: "Scores hypotheses by confidence & business value",
        Icon: Scale,
        color: "#fbbf24", // amber
    },
    viz: {
        id: "viz",
        name: "Viz Whiz",
        description: "Auto-generates interactive charts",
        Icon: BarChart3,
        color: "#34d399", // emerald
    },
    nlq: {
        id: "nlq",
        name: "Query Agent",
        description: "Writes and runs analysis code for your question",
        Icon: Bot,
        color: "#e879f9", // magenta
    },
};

export const ANALYSIS_FLOW = ["janitor", "hypothesis", "debate", "viz"] as const;
export const NLQ_FLOW = ["janitor", "nlq", "viz"] as const;

export function metaFor(id: string): AgentMeta {
    return (
        AGENT_META[id] ?? {
            id,
            name: id,
            description: "",
            Icon: Bot,
            color: "#94a3b8",
        }
    );
}
