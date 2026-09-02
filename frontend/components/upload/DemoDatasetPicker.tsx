"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { ArrowRight, Database, Loader2 } from "lucide-react";
import { DemoDataset, ParseAssumptions } from "@/lib/types";

interface UploadInfo {
    type: "uploaded" | "demo";
    name: string;
    rows: number | string;
    columns: number | string;
    description?: string;
    use_cases?: string[];
    assumptions?: ParseAssumptions;
}

/**
 * The landing screen's primary path: every demo dataset shown at once, ready
 * to click. This used to be a collapsed dropdown nested under the upload
 * box — the least visible thing on the screen even though it's the fastest
 * way for a first-time visitor (no CSV in hand yet) to see the product work.
 */
export function DemoDatasetPicker({
    onUploadSuccess,
    datasets,
}: {
    onUploadSuccess: (datasetId: string, info: UploadInfo) => void;
    datasets: Record<string, DemoDataset>;
}) {
    const [loadingId, setLoadingId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const getErrorMessage = (err: unknown, fallback: string) => {
        if (typeof err === "object" && err !== null && "response" in err) {
            const response = (err as { response?: { data?: { detail?: string } } }).response;
            if (response?.data?.detail) return response.data.detail;
        }
        return err instanceof Error ? err.message : fallback;
    };

    const loadDemo = async (datasetId: string) => {
        if (loadingId) return;
        setError(null);
        setLoadingId(datasetId);
        try {
            const result = await api.loadDemoData(datasetId);
            onUploadSuccess(result.dataset_id, {
                name: result.dataset_name,
                type: "demo",
                rows: result.row_count,
                columns: result.column_count,
                description: result.description,
                use_cases: result.use_cases,
            });
        } catch (err: unknown) {
            setError(getErrorMessage(err, "Failed to load demo"));
            setLoadingId(null);
        }
    };

    return (
        <div className="w-full space-y-2">
            {Object.entries(datasets).map(([id, config]) => {
                const loading = loadingId === id;
                return (
                    <button
                        key={id}
                        onClick={() => loadDemo(id)}
                        disabled={loadingId !== null}
                        className="group flex w-full items-center gap-3 rounded-xl border border-border bg-surface p-3.5 text-left transition-colors hover:border-accent/50 hover:bg-surface-2 disabled:cursor-default disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-surface"
                    >
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-accent-soft/50 text-accent">
                            <Database size={17} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-fg">{config.name}</span>
                            <span className="mt-0.5 block truncate text-xs text-faint">{config.description}</span>
                            <span className="mt-1.5 flex gap-2">
                                <span className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-muted">
                                    {config.rows} rows
                                </span>
                                <span className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-muted">
                                    {config.columns} cols
                                </span>
                            </span>
                        </span>
                        {loading ? (
                            <Loader2 size={16} className="shrink-0 animate-spin text-accent" />
                        ) : (
                            <ArrowRight
                                size={16}
                                className="shrink-0 text-faint opacity-0 transition-all group-hover:translate-x-0.5 group-hover:text-accent group-hover:opacity-100"
                            />
                        )}
                    </button>
                );
            })}

            {error && (
                <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{error}</div>
            )}
        </div>
    );
}
