"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { ProcessResponse } from "@/lib/types";
import { AgentTimeline, Agent } from "@/components/agents/AgentTimeline";
import { ANALYSIS_FLOW, NLQ_FLOW } from "@/lib/agents";
import { MessageBubble, ChatMessage } from "@/components/chat/MessageBubble";
import { CanvasPane, QueryResult } from "./CanvasPane";
import type { SavedState } from "@/lib/workspaces";

interface WorkspaceProps {
    workspaceId: string;
    datasetId: string;
    datasetName: string;
    restore?: SavedState | null;
    onPersist: (state: SavedState) => void;
    onCost?: (delta: { tokens: number; cost: number }) => void;
}

export function Workspace({ workspaceId, datasetId, datasetName, restore, onPersist, onCost }: WorkspaceProps) {
    const sessionId = workspaceId;
    const reopened = !!restore?.analysisResult;

    const [analysisLoading, setAnalysisLoading] = useState(!reopened);
    const [analysisResult, setAnalysisResult] = useState<ProcessResponse | null>(restore?.analysisResult ?? null);
    const [analysisError, setAnalysisError] = useState<string | null>(null);

    const [messages, setMessages] = useState<ChatMessage[]>(restore?.messages ?? []);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [nlqRunId, setNlqRunId] = useState<number | null>(null);

    // Query results drive the canvas (charts render big on the wide side).
    const [results, setResults] = useState<QueryResult[]>(restore?.results ?? []);
    const [pinned, setPinned] = useState<number[]>(restore?.pinned ?? []);
    const [canvasTab, setCanvasTab] = useState<"overview" | "results">(
        restore?.results.length ? "results" : "overview"
    );

    const persistRef = useRef(onPersist);
    persistRef.current = onPersist;
    const costRef = useRef(onCost);
    costRef.current = onCost;
    // Strictly increasing chart ids. Date.now() alone collides when two
    // results arrive in the same millisecond, which duplicates React keys.
    const resultSeq = useRef<number>(Date.now());

    const togglePin = useCallback((id: number) => {
        setPinned((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
    }, []);

    const liveAgents = useRef<Agent[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // ── Auto-analysis on mount (skipped when reopening a saved run) ──────
    useEffect(() => {
        if (reopened) return;
        let cancelled = false;
        setAnalysisLoading(true);
        setAnalysisError(null);
        api.processData(datasetId, sessionId)
            .then((result) => {
                if (!cancelled) setAnalysisResult(result);
            })
            .catch((e) => {
                if (!cancelled) setAnalysisError(e instanceof Error ? e.message : "Analysis failed.");
            })
            .finally(() => {
                if (!cancelled) setAnalysisLoading(false);
            });
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [datasetId]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, isLoading, analysisLoading, analysisResult]);

    // Persist the workspace whenever meaningful state changes.
    useEffect(() => {
        if (!analysisResult) return;
        persistRef.current({ analysisResult, messages, results, pinned });
    }, [analysisResult, messages, results, pinned]);

    const errMessage = (error: unknown): string => {
        if (typeof error === "object" && error !== null && "response" in error) {
            const r = (error as { response?: { data?: { detail?: string } } }).response;
            if (r?.data?.detail) return r.data.detail;
        }
        return error instanceof Error ? error.message : "Something went wrong.";
    };

    const submitQuery = useCallback(
        async (q: string) => {
            const question = q.trim();
            if (!question || isLoading || analysisLoading) return;

            setInput("");
            setMessages((p) => [...p, { role: "user", content: question }]);
            setIsLoading(true);
            liveAgents.current = [];
            setNlqRunId((k) => (k ?? 0) + 1);

            try {
                const res = await api.naturalLanguageQuery({
                    dataset_id: datasetId,
                    question,
                    session_id: sessionId,
                });
                if (res.tokens_used || res.cost_usd) {
                    costRef.current?.({ tokens: res.tokens_used ?? 0, cost: res.cost_usd ?? 0 });
                }
                const resultId = res.plot_json ? (resultSeq.current += 1) : undefined;
                if (res.plot_json && resultId) {
                    setResults((prev) => [
                        { id: resultId, question, answer: res.answer, plotJson: res.plot_json! },
                        ...prev,
                    ]);
                    setCanvasTab("results");
                }
                setMessages((p) => [
                    ...p,
                    {
                        role: "assistant",
                        content: res.answer,
                        code: res.code,
                        reasoning: res.reasoning,
                        agents: [...liveAgents.current],
                        chartResultId: resultId,
                    },
                ]);
            } catch (error) {
                setMessages((p) => [
                    ...p,
                    { role: "assistant", content: errMessage(error), isError: true, agents: [...liveAgents.current] },
                ]);
            } finally {
                setIsLoading(false);
            }
        },
        [datasetId, sessionId, isLoading, analysisLoading]
    );

    const refineResult = useCallback(
        (r: QueryResult, instruction: string) => {
            setCanvasTab("results");
            void submitQuery(`Based on the previous chart for "${r.question}", ${instruction}. Produce an updated chart.`);
        },
        [submitQuery]
    );

    const suggested = analysisResult?.suggested_questions ?? [];

    return (
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(380px,2fr)_minmax(0,3fr)]">
            {/* ── Conversation pane ─────────────────────────────────────── */}
            <section className="flex min-h-0 flex-col border-border lg:border-r">
                <div className="flex items-center gap-2 border-b border-border px-5 py-3">
                    <Sparkles size={15} className="text-accent" />
                    <h2 className="text-sm font-semibold text-fg">Conversation</h2>
                </div>

                <div ref={scrollRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
                    {/* Live analysis pipeline */}
                    {analysisLoading && (
                        <div className="rounded-2xl border border-border bg-surface p-4">
                            <p className="mb-3 flex items-center gap-2 text-xs font-medium text-muted">
                                <Loader2 size={13} className="animate-spin text-accent" />
                                The orchestra is analyzing <span className="text-fg">{datasetName}</span>…
                            </p>
                            <AgentTimeline
                                sessionId={sessionId}
                                flow={ANALYSIS_FLOW}
                                runId={1}
                                finished={false}
                            />
                        </div>
                    )}

                    {analysisError && (
                        <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
                            Could not complete analysis: {analysisError}
                        </div>
                    )}

                    {/* Narrative intro */}
                    {analysisResult && !analysisLoading && (
                        <MessageBubble
                            role="assistant"
                            content={analysisResult.narrative}
                            intro
                            stream
                        />
                    )}

                    {/* Sampling notice — never imply the analysis covered
                        rows it never saw. */}
                    {analysisResult?.sampling?.sampled && (
                        <div className="rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-xs text-muted">
                            Analysed the first{" "}
                            <span className="font-medium text-fg">
                                {analysisResult.sampling.analyzed_rows.toLocaleString()}
                            </span>{" "}
                            of{" "}
                            <span className="font-medium text-fg">
                                {analysisResult.sampling.total_rows.toLocaleString()}
                            </span>{" "}
                            rows. Raise <code className="font-mono">MAX_ANALYSIS_ROWS</code> to cover the whole file.
                        </div>
                    )}

                    {/* Suggested questions */}
                    {suggested.length > 0 && messages.length === 0 && !isLoading && (
                        <div className="space-y-2">
                            <p className="text-xs font-medium text-faint">Suggested questions</p>
                            <div className="flex flex-col gap-2">
                                {suggested.map((s, i) => (
                                    <button
                                        key={i}
                                        onClick={() => submitQuery(s)}
                                        className="group flex items-center gap-2 rounded-xl border border-border bg-surface px-3.5 py-2.5 text-left text-sm text-muted transition-colors hover:border-accent/50 hover:text-fg"
                                    >
                                        <Sparkles size={13} className="shrink-0 text-accent opacity-60 group-hover:opacity-100" />
                                        {s}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Conversation */}
                    {messages.map((m, i) => (
                        <MessageBubble
                            key={i}
                            {...m}
                            onViewChart={() => setCanvasTab("results")}
                            stream={i === messages.length - 1 && m.role === "assistant" && !isLoading}
                        />
                    ))}

                    {/* Live NLQ pipeline */}
                    {isLoading && (
                        <div className="rounded-2xl border border-border bg-surface p-4">
                            <AgentTimeline
                                sessionId={sessionId}
                                flow={NLQ_FLOW}
                                runId={nlqRunId}
                                finished={false}
                                onAgentsChange={(a) => (liveAgents.current = a)}
                            />
                        </div>
                    )}
                </div>

                {/* Input */}
                <div className="border-t border-border bg-surface/60 p-3">
                    {/* Quick follow-ups */}
                    {suggested.length > 0 && !analysisLoading && messages.length > 0 && (
                        <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
                            {suggested.slice(0, 5).map((s, i) => (
                                <button
                                    key={i}
                                    onClick={() => submitQuery(s)}
                                    disabled={isLoading}
                                    className="shrink-0 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-muted transition-colors hover:border-accent/50 hover:text-fg disabled:opacity-50"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    )}
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            void submitQuery(input);
                        }}
                        className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-1.5 transition-all focus-within:border-accent/60 focus-within:shadow-[0_0_0_3px_var(--ring)]"
                    >
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    void submitQuery(input);
                                }
                            }}
                            placeholder={analysisLoading ? "Analyzing your data…" : "Ask a question about your data…"}
                            disabled={isLoading || analysisLoading}
                            rows={1}
                            className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-3 py-2 text-sm text-fg outline-none placeholder:text-faint disabled:opacity-60"
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading || analysisLoading}
                            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40"
                        >
                            {isLoading ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
                        </button>
                    </form>
                    <p className="mt-2 text-center text-[11px] text-faint">
                        Insight Orchestra can make mistakes — review the generated code.
                    </p>
                </div>
            </section>

            {/* ── Canvas pane ───────────────────────────────────────────── */}
            <CanvasPane
                loading={analysisLoading}
                error={analysisError}
                result={analysisResult}
                datasetName={datasetName}
                results={results}
                pinned={pinned}
                onTogglePin={togglePin}
                onRefine={refineResult}
                activeTab={canvasTab}
                onTab={setCanvasTab}
            />
        </div>
    );
}
