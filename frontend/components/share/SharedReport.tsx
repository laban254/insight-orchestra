"use client";

import Link from "next/link";
import { Waypoints, TrendingUp, ArrowUpRight } from "lucide-react";
import { ProcessResponse } from "@/lib/types";
import { ChartRenderer } from "@/components/viz/ChartRenderer";

export interface SharedPayload {
    datasetName: string;
    analysisResult: ProcessResponse;
    results: { id: number; question: string; answer: string; plotJson: string }[];
}

function Stat({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-[11px] font-medium uppercase tracking-wider text-faint">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{value}</p>
        </div>
    );
}

export function SharedReport({ datasetName, analysisResult, results }: SharedPayload) {
    const report = analysisResult.cleaner.report;
    const consensus = analysisResult.debate.summary.consensus;
    const plots = analysisResult.viz.chart_info.plots ?? [];

    return (
        <main className="min-h-screen bg-bg">
            <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/80 px-4 py-3 backdrop-blur">
                <div className="flex items-center gap-2.5">
                    <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-accent-fg">
                        <Waypoints size={18} />
                    </span>
                    <div>
                        <p className="text-sm font-semibold text-fg">{datasetName}</p>
                        <p className="text-[11px] text-faint">Shared analysis · read-only</p>
                    </div>
                </div>
                <Link
                    href="/"
                    className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-accent-fg transition-opacity hover:opacity-90"
                >
                    Open Insight Orchestra <ArrowUpRight size={14} />
                </Link>
            </header>

            <div className="mx-auto max-w-4xl space-y-7 px-4 py-8">
                <section className="rounded-2xl border border-border bg-surface p-5">
                    <p className="leading-relaxed text-muted">{analysisResult.narrative}</p>
                </section>

                <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="Rows" value={report.final_shape[0].toLocaleString()} />
                    <Stat label="Columns" value={report.final_shape[1]} />
                    <Stat label="Duplicates removed" value={report.duplicates_removed.toLocaleString()} />
                    <Stat label="Missing fixed" value={report.total_missing.toLocaleString()} />
                </section>

                {consensus && (
                    <section className="rounded-2xl border border-accent/30 bg-accent-soft/20 p-5">
                        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-accent">
                            <TrendingUp size={13} /> Top insight · {Math.round(consensus.confidence * 100)}% confidence
                        </p>
                        <p className="mt-2 text-[15px] text-fg">{consensus.hypothesis}</p>
                        {consensus.statistical_argument && (
                            <p className="mt-1.5 text-sm leading-relaxed text-muted">{consensus.statistical_argument}</p>
                        )}
                    </section>
                )}

                {plots.length > 0 && (
                    <section className="space-y-4">
                        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-faint">Charts</h2>
                        {plots.map((p, i) => (
                            <div key={i} className="rounded-2xl border border-border bg-surface p-3">
                                <ChartRenderer plotJsonStr={p.plotly_json} height={400} />
                            </div>
                        ))}
                    </section>
                )}

                {results.length > 0 && (
                    <section className="space-y-4">
                        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-faint">Query results</h2>
                        {results.map((r) => (
                            <div key={r.id} className="space-y-2 rounded-2xl border border-border bg-surface p-3">
                                <p className="px-1 text-sm font-medium text-fg">{r.question}</p>
                                <ChartRenderer plotJsonStr={r.plotJson} height={400} />
                            </div>
                        ))}
                    </section>
                )}

                <p className="pb-8 text-center text-xs text-faint">
                    Generated with Insight Orchestra · a multi-agent data analysis workspace
                </p>
            </div>
        </main>
    );
}
