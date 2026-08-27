"use client";

import { useState } from "react";
import { LayoutDashboard, TrendingUp, Lightbulb, AlertTriangle, Rows3, Columns3, CopyMinus, Wand2, BarChart3, MessageSquare, Pin, Columns2, Wand, CornerDownLeft } from "lucide-react";
import { ProcessResponse, ScoredHypothesis } from "@/lib/types";
import { ChartRenderer } from "@/components/viz/ChartRenderer";
import { DataTable } from "@/components/viz/DataTable";

export interface QueryResult {
    id: number;
    question: string;
    answer: string;
    plotJson: string;
}

interface CanvasPaneProps {
    loading: boolean;
    error: string | null;
    result: ProcessResponse | null;
    datasetName: string;
    results: QueryResult[];
    pinned: number[];
    onTogglePin: (id: number) => void;
    onRefine: (r: QueryResult, instruction: string) => void;
    activeTab: "overview" | "results";
    onTab: (t: "overview" | "results") => void;
}

function ResultCard({
    r,
    pinned,
    onTogglePin,
    onRefine,
    height,
    compact,
}: {
    r: QueryResult;
    pinned: boolean;
    onTogglePin: (id: number) => void;
    onRefine?: (instruction: string) => void;
    height: number;
    compact?: boolean;
}) {
    const [refine, setRefine] = useState("");
    const submit = () => {
        const v = refine.trim();
        if (v && onRefine) {
            onRefine(v);
            setRefine("");
        }
    };
    return (
        <div className="animate-rise space-y-2.5">
            <div className="flex items-start gap-2">
                <MessageSquare size={14} className="mt-0.5 shrink-0 text-accent-2" />
                <p className={`flex-1 font-medium text-fg ${compact ? "text-xs" : "text-sm"}`}>{r.question}</p>
                <button
                    onClick={() => onTogglePin(r.id)}
                    title={pinned ? "Unpin" : "Pin to compare"}
                    className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg border transition-colors ${
                        pinned
                            ? "border-accent/40 bg-accent-soft/40 text-accent"
                            : "border-border bg-surface text-faint hover:text-fg"
                    }`}
                >
                    <Pin size={13} className={pinned ? "fill-current" : ""} />
                </button>
            </div>
            <ChartRenderer plotJsonStr={r.plotJson} height={height} />
            {!compact && onRefine && (
                <div className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-2 py-1.5 focus-within:border-accent/50">
                    <Wand size={14} className="ml-1 shrink-0 text-accent-2" />
                    <input
                        value={refine}
                        onChange={(e) => setRefine(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && submit()}
                        placeholder="Refine this chart — e.g. make it a bar chart, color by region…"
                        className="flex-1 bg-transparent py-1 text-xs text-fg outline-none placeholder:text-faint"
                    />
                    <button
                        onClick={submit}
                        disabled={!refine.trim()}
                        className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent-2/15 text-accent-2 transition-opacity hover:opacity-80 disabled:opacity-30"
                    >
                        <CornerDownLeft size={13} />
                    </button>
                </div>
            )}
        </div>
    );
}

function Stat({ icon: Icon, label, value, tint }: { icon: typeof Rows3; label: string; value: string; tint: string }) {
    return (
        <div className="rounded-xl border border-border bg-surface p-3.5">
            <div className="mb-2 flex items-center gap-1.5 text-faint">
                <Icon size={14} style={{ color: tint }} />
                <span className="text-[11px] font-medium uppercase tracking-wide">{label}</span>
            </div>
            <p className="font-mono text-xl font-semibold text-fg">{value}</p>
        </div>
    );
}

function Meter({ label, value, color }: { label: string; value: number | null; color: string }) {
    // A null score means nothing assessed this claim. Showing an empty bar would read as
    // "scored zero", so say so in words and drop the bar entirely.
    if (value == null || Number.isNaN(value)) {
        return (
            <div>
                <div className="mb-1 flex items-center justify-between text-[11px]">
                    <span className="text-faint">{label}</span>
                    <span className="font-mono font-medium text-faint">not assessed</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full border border-dashed border-border-soft bg-transparent" />
            </div>
        );
    }
    const pct = Math.round(value * 100);
    return (
        <div>
            <div className="mb-1 flex items-center justify-between text-[11px]">
                <span className="text-faint">{label}</span>
                <span className="font-mono font-medium text-muted">{pct}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
            </div>
        </div>
    );
}

function Skeleton() {
    return (
        <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="relative h-[88px] overflow-hidden rounded-xl border border-border bg-surface-2">
                        <div className="shimmer absolute inset-0" />
                    </div>
                ))}
            </div>
            {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="relative h-[340px] overflow-hidden rounded-2xl border border-border bg-surface-2">
                    <div className="shimmer absolute inset-0" />
                </div>
            ))}
        </div>
    );
}

export function CanvasPane({ loading, error, result, datasetName, results, pinned, onTogglePin, onRefine, activeTab, onTab }: CanvasPaneProps) {
    const report = result?.cleaner.report;
    const pinnedResults = pinned
        .map((id) => results.find((r) => r.id === id))
        .filter((r): r is QueryResult => Boolean(r));
    const consensus = result?.debate.summary.consensus;
    const scored = result?.debate.scored_hypotheses ?? [];
    const plots = result?.viz.chart_info.plots ?? [];
    const numeric = result?.hypothesis.summary.numeric_columns ?? [];
    const categorical = result?.hypothesis.summary.categorical_columns ?? [];
    const flags = [...(report?.bias_flags ?? []), ...(report?.outlier_flags ?? [])];
    const preview = result?.preview;

    const others = scored.filter((h) => h.hypothesis !== consensus?.hypothesis).slice(0, 4);

    const tabBtn = (id: "overview" | "results", label: string, Icon: typeof LayoutDashboard, count?: number) => {
        const on = activeTab === id;
        return (
            <button
                onClick={() => onTab(id)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    on ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"
                }`}
            >
                <Icon size={14} className={on ? "text-accent-2" : ""} />
                {label}
                {count != null && count > 0 && (
                    <span className="rounded-full bg-accent-2/20 px-1.5 text-[10px] font-semibold text-accent-2">{count}</span>
                )}
            </button>
        );
    };

    return (
        <section className="flex min-h-0 flex-col bg-bg">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                {tabBtn("overview", "Overview", LayoutDashboard)}
                {tabBtn("results", "Results", BarChart3, results.length)}
                <span className="ml-auto truncate text-xs text-faint">{datasetName}</span>
            </div>

            {activeTab === "results" ? (
                <div className="min-h-0 flex-1 overflow-y-auto p-5">
                    {results.length === 0 ? (
                        <div className="flex h-full items-center justify-center">
                            <div className="max-w-xs text-center">
                                <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-surface-2 text-accent-2">
                                    <BarChart3 size={22} />
                                </div>
                                <p className="text-sm font-medium text-fg">No query results yet</p>
                                <p className="mt-1 text-xs text-faint">
                                    Ask a question in the conversation and any chart you generate will appear here, full-size.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-7">
                            {/* Pinned — side-by-side compare */}
                            {pinnedResults.length > 0 && (
                                <div>
                                    <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-accent">
                                        <Columns2 size={13} /> Pinned · compare
                                    </h3>
                                    <div className={`grid gap-4 ${pinnedResults.length > 1 ? "2xl:grid-cols-2" : "grid-cols-1"}`}>
                                        {pinnedResults.map((r) => (
                                            <ResultCard
                                                key={`pin-${r.id}`}
                                                r={r}
                                                pinned
                                                onTogglePin={onTogglePin}
                                                height={300}
                                                compact
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* All results — newest first */}
                            <div>
                                {pinnedResults.length > 0 && (
                                    <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-faint">All results</h3>
                                )}
                                <div className="space-y-6">
                                    {results.map((r) => (
                                        <ResultCard
                                            key={r.id}
                                            r={r}
                                            pinned={pinned.includes(r.id)}
                                            onTogglePin={onTogglePin}
                                            onRefine={(instr) => onRefine(r, instr)}
                                            height={460}
                                        />
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            ) : (
            <div className="min-h-0 flex-1 overflow-y-auto p-5">
                {loading && <Skeleton />}

                {error && !loading && (
                    <div className="flex h-full items-center justify-center">
                        <div className="max-w-sm rounded-2xl border border-danger/30 bg-danger/10 p-6 text-center">
                            <AlertTriangle size={22} className="mx-auto mb-2 text-danger" />
                            <p className="text-sm text-danger">{error}</p>
                        </div>
                    </div>
                )}

                {result && !loading && report && (
                    <div className="animate-fade space-y-6">
                        {/* KPI row */}
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            <Stat icon={Rows3} label="Rows" value={report.final_shape[0].toLocaleString()} tint="#22d3ee" />
                            <Stat icon={Columns3} label="Columns" value={String(report.final_shape[1])} tint="#a78bfa" />
                            <Stat icon={CopyMinus} label="Dupes removed" value={report.duplicates_removed.toLocaleString()} tint="#fbbf24" />
                            <Stat icon={Wand2} label="Missing fixed" value={report.total_missing.toLocaleString()} tint="#34d399" />
                        </div>

                        {/* Top insight */}
                        {consensus && (
                            <div className="rounded-2xl border border-accent/30 bg-accent-soft/40 p-5">
                                <div className="mb-2 flex items-center gap-2">
                                    <TrendingUp size={15} className="text-accent" />
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">
                                        Top insight
                                    </span>
                                </div>
                                <p className="text-[15px] font-medium leading-relaxed text-fg">{consensus.hypothesis}</p>
                                {consensus.statistical_argument && (
                                    <p className="mt-2 text-xs leading-relaxed text-muted">{consensus.statistical_argument}</p>
                                )}
                                <div className="mt-4 grid grid-cols-2 gap-4">
                                    <Meter label="Confidence" value={consensus.confidence} color="#22d3ee" />
                                    <Meter label="Business value" value={consensus.business_value} color="#e879f9" />
                                </div>
                            </div>
                        )}

                        {/* Charts grid */}
                        {plots.length > 0 && (
                            <div>
                                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-faint">
                                    {plots.length} chart{plots.length > 1 ? "s" : ""}
                                </h3>
                                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                                    {plots.map((p, i) => (
                                        <div key={i} className="space-y-1.5">
                                            {p.title && <p className="px-1 text-xs font-medium text-muted">{p.title}</p>}
                                            <ChartRenderer plotJsonStr={p.plotly_json} height={300} />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Other patterns */}
                        {others.length > 0 && (
                            <div>
                                <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-faint">
                                    <Lightbulb size={13} className="text-warning" /> Other patterns
                                </h3>
                                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                    {others.map((h: ScoredHypothesis, i) => (
                                        <div key={i} className="rounded-xl border border-border bg-surface p-3.5">
                                            <p className="text-sm leading-relaxed text-muted">{h.hypothesis}</p>
                                            <div className="mt-3 grid grid-cols-2 gap-3">
                                                <Meter label="Confidence" value={h.confidence} color="#a78bfa" />
                                                <Meter label="Value" value={h.business_value} color="#34d399" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Data preview */}
                        {preview && preview.rows.length > 0 && (
                            <DataTable columns={preview.columns} data={preview.rows} />
                        )}

                        {/* Columns + data quality */}
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            {(numeric.length > 0 || categorical.length > 0) && (
                                <div className="rounded-xl border border-border bg-surface p-4">
                                    <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-faint">Columns</h3>
                                    <div className="flex flex-wrap gap-1.5">
                                        {numeric.map((c) => (
                                            <span key={c} className="rounded-md bg-accent-soft/50 px-2 py-1 font-mono text-[11px] text-accent">
                                                {c}
                                            </span>
                                        ))}
                                        {categorical.map((c) => (
                                            <span key={c} className="rounded-md bg-surface-2 px-2 py-1 font-mono text-[11px] text-muted">
                                                {c}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {flags.length > 0 && (
                                <div className="rounded-xl border border-warning/30 bg-warning/5 p-4">
                                    <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-warning">
                                        <AlertTriangle size={13} /> Data quality flags
                                    </h3>
                                    <ul className="space-y-1.5">
                                        {flags.map((f, i) => (
                                            <li key={i} className="flex gap-2 text-xs leading-relaxed text-muted">
                                                <span className="text-warning">•</span>
                                                {f}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
            )}
        </section>
    );
}
