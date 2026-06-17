"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Lightbulb, User, Sparkles, BarChart3, ArrowRight } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { PipelineSummary } from "../agents/PipelineSummary";
import type { Agent } from "../agents/AgentTimeline";

/** Progressively reveals text word-by-word for a live "typing" feel. */
function useReveal(text: string, enabled: boolean) {
    const [n, setN] = useState(enabled ? 0 : text.length);
    useEffect(() => {
        if (!enabled) {
            setN(text.length);
            return;
        }
        setN(0);
        const tokens = text.split(/(\s+)/);
        let i = 0;
        const id = setInterval(() => {
            i += 1;
            const upto = tokens.slice(0, i).join("").length;
            setN(upto);
            if (upto >= text.length) clearInterval(id);
        }, 22);
        return () => clearInterval(id);
    }, [text, enabled]);
    return { shown: text.slice(0, n), done: n >= text.length };
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    code?: string | null;
    reasoning?: string | null;
    isError?: boolean;
    agents?: Agent[];
    /** Set when this answer produced a chart shown on the canvas. */
    chartResultId?: number;
    /** The opening narrative message rendered without the chat avatar chrome. */
    intro?: boolean;
}

interface MessageBubbleProps extends ChatMessage {
    onViewChart?: () => void;
    /** Reveal the answer progressively (newest message only). */
    stream?: boolean;
}

const md = {
    p: (p: React.HTMLAttributes<HTMLParagraphElement>) => <p className="mb-2 last:mb-0 leading-relaxed" {...p} />,
    strong: (p: React.HTMLAttributes<HTMLElement>) => <strong className="font-semibold text-fg" {...p} />,
    ul: (p: React.HTMLAttributes<HTMLUListElement>) => <ul className="mb-2 ml-4 list-disc space-y-1" {...p} />,
    ol: (p: React.HTMLAttributes<HTMLOListElement>) => <ol className="mb-2 ml-4 list-decimal space-y-1" {...p} />,
    li: (p: React.HTMLAttributes<HTMLLIElement>) => <li className="leading-relaxed" {...p} />,
    a: (p: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a className="text-accent underline underline-offset-2" {...p} />,
    code: (p: React.HTMLAttributes<HTMLElement>) => (
        <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[0.85em] text-accent" {...p} />
    ),
    h1: (p: React.HTMLAttributes<HTMLHeadingElement>) => <h3 className="mb-2 mt-1 text-base font-semibold text-fg" {...p} />,
    h2: (p: React.HTMLAttributes<HTMLHeadingElement>) => <h3 className="mb-2 mt-1 text-base font-semibold text-fg" {...p} />,
    h3: (p: React.HTMLAttributes<HTMLHeadingElement>) => <h4 className="mb-1.5 mt-1 text-sm font-semibold text-fg" {...p} />,
    table: (p: React.HTMLAttributes<HTMLTableElement>) => (
        <div className="my-3 overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-xs" {...p} />
        </div>
    ),
    th: (p: React.HTMLAttributes<HTMLTableCellElement>) => (
        <th className="border-b border-border bg-surface-2 px-3 py-2 font-semibold text-fg" {...p} />
    ),
    td: (p: React.HTMLAttributes<HTMLTableCellElement>) => <td className="border-b border-border-soft px-3 py-2 text-muted" {...p} />,
    blockquote: (p: React.HTMLAttributes<HTMLQuoteElement>) => (
        <blockquote className="my-2 border-l-2 border-accent/50 pl-3 text-muted" {...p} />
    ),
};

function Markdown({ children }: { children: string }) {
    return (
        <div className="text-sm text-muted">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={md}>
                {children}
            </ReactMarkdown>
        </div>
    );
}

export function MessageBubble({ role, content, code, reasoning, isError, agents, intro, chartResultId, onViewChart, stream }: MessageBubbleProps) {
    const isUser = role === "user";
    const [showReasoning, setShowReasoning] = useState(false);
    const { shown, done } = useReveal(content, !!stream && !isUser && !isError);

    if (isUser) {
        return (
            <div className="flex justify-end gap-2.5">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-4 py-2.5 text-sm leading-relaxed text-accent-fg">
                    {content}
                </div>
                <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted">
                    <User size={14} />
                </div>
            </div>
        );
    }

    return (
        <div className="flex gap-2.5">
            <div
                className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg ${
                    isError ? "bg-danger/15 text-danger" : "bg-accent-2/15 text-accent-2"
                }`}
            >
                <Sparkles size={14} />
            </div>

            <div className="min-w-0 flex-1 space-y-2.5">
                {agents && agents.length > 0 && <PipelineSummary agents={agents} />}

                {content && (
                    <div
                        className={`rounded-2xl rounded-tl-sm border px-4 py-3 ${
                            isError
                                ? "border-danger/30 bg-danger/10 text-danger"
                                : intro
                                  ? "border-border bg-gradient-to-br from-surface to-surface-2"
                                  : "border-border bg-surface"
                        }`}
                    >
                        {isError ? (
                            <p className="text-sm leading-relaxed">{content}</p>
                        ) : (
                            <div className="relative">
                                <Markdown>{stream ? shown : content}</Markdown>
                                {stream && !done && (
                                    <span className="ml-0.5 inline-block h-3.5 w-1.5 -translate-y-px animate-pulse rounded-sm bg-accent align-middle" />
                                )}
                            </div>
                        )}
                    </div>
                )}

                {chartResultId && (
                    <button
                        onClick={onViewChart}
                        className="group flex items-center gap-2 rounded-xl border border-accent/30 bg-accent-soft/30 px-3.5 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent-soft/50"
                    >
                        <BarChart3 size={15} />
                        Chart added to the Canvas
                        <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                    </button>
                )}

                {reasoning && !isError && (
                    <div>
                        <button
                            onClick={() => setShowReasoning((v) => !v)}
                            className="flex items-center gap-1.5 text-xs font-medium text-accent-2 transition-opacity hover:opacity-80"
                        >
                            <Lightbulb size={13} className={showReasoning ? "fill-current" : ""} />
                            {showReasoning ? "Hide reasoning" : "How I figured this out"}
                        </button>
                        {showReasoning && (
                            <div className="mt-1.5 rounded-xl border border-border bg-surface-2 p-3.5 text-xs leading-relaxed text-muted">
                                {reasoning}
                            </div>
                        )}
                    </div>
                )}

                {code && <CodeBlock code={code} language="python" />}
            </div>
        </div>
    );
}
