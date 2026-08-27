"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { ChevronDown, UploadCloud, Database, Loader2 } from "lucide-react";
import { DemoDataset } from "@/lib/types";

interface UploadInfo {
    type: "uploaded" | "demo";
    name: string;
    rows: number | string;
    columns: number | string;
    description?: string;
    use_cases?: string[];
}

export function DatasetSelector({
    onUploadSuccess,
    datasets,
}: {
    onUploadSuccess: (filePath: string, info: UploadInfo) => void;
    datasets: Record<string, DemoDataset>;
}) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showDatasets, setShowDatasets] = useState(false);
    const [selectedDataset, setSelectedDataset] = useState<string | null>(null);

    const getErrorMessage = (err: unknown, fallback: string) => {
        if (typeof err === "object" && err !== null && "response" in err) {
            const response = (err as { response?: { data?: { detail?: string } } }).response;
            if (response?.data?.detail) return response.data.detail;
        }
        return err instanceof Error ? err.message : fallback;
    };

    const uploadFile = useCallback(
        async (file: File) => {
            setError(null);
            setIsUploading(true);
            try {
                const result = await api.uploadFile(file);
                onUploadSuccess(result.file_path, {
                    name: file.name,
                    type: "uploaded",
                    rows: result.rows || "Unknown",
                    columns: result.columns || "Unknown",
                });
            } catch (err: unknown) {
                setError(getErrorMessage(err, "Upload failed"));
            } finally {
                setIsUploading(false);
            }
        },
        [onUploadSuccess]
    );

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(e.type === "dragenter" || e.type === "dragover");
    }, []);

    const handleDrop = useCallback(
        async (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            if (e.dataTransfer.files?.[0]) await uploadFile(e.dataTransfer.files[0]);
        },
        [uploadFile]
    );

    const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.[0]) await uploadFile(e.target.files[0]);
    };

    const loadDemo = async (datasetId: string) => {
        setError(null);
        setIsUploading(true);
        setSelectedDataset(datasetId);
        try {
            const result = await api.loadDemoData(datasetId);
            onUploadSuccess(result.file_path, {
                name: result.dataset_name,
                type: "demo",
                rows: result.row_count,
                columns: result.column_count,
                description: result.description,
                use_cases: result.use_cases,
            });
            setShowDatasets(false);
        } catch (err: unknown) {
            setError(getErrorMessage(err, "Failed to load demo"));
        } finally {
            setIsUploading(false);
            setSelectedDataset(null);
        }
    };

    return (
        <div className="w-full space-y-4">
            {/* Dropzone */}
            <div
                className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                    isDragging ? "border-accent bg-accent-soft/30" : "border-border hover:border-accent/50"
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input type="file" accept=".csv" className="hidden" id="file-upload" onChange={handleChange} />
                <label htmlFor="file-upload" className="flex cursor-pointer flex-col items-center gap-2">
                    {isUploading && !selectedDataset ? (
                        <>
                            <Loader2 size={26} className="animate-spin text-accent" />
                            <p className="text-sm font-medium text-accent">Uploading…</p>
                        </>
                    ) : (
                        <>
                            <div className="grid h-12 w-12 place-items-center rounded-xl bg-surface-2 text-accent">
                                <UploadCloud size={22} />
                            </div>
                            <p className="text-sm font-medium text-fg">Click to upload or drag and drop</p>
                            <p className="text-xs text-faint">CSV files only</p>
                        </>
                    )}
                </label>
            </div>

            {error && (
                <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{error}</div>
            )}

            {/* Demo datasets */}
            <div className="space-y-2">
                <div className="flex items-center gap-3">
                    <div className="h-px flex-1 bg-border" />
                    <span className="text-xs font-medium text-faint">or try a demo dataset</span>
                    <div className="h-px flex-1 bg-border" />
                </div>

                <div className="relative">
                    <button
                        onClick={() => setShowDatasets((v) => !v)}
                        disabled={isUploading}
                        aria-expanded={showDatasets}
                        aria-haspopup="listbox"
                        aria-controls="demo-dataset-list"
                        className="flex w-full items-center justify-between rounded-xl border border-border bg-surface px-4 py-3 text-left transition-colors hover:border-accent/50 disabled:opacity-50"
                    >
                        <span className="flex items-center gap-2 text-sm font-medium text-fg">
                            <Database size={15} className="text-accent-2" />
                            {selectedDataset ? `Loading ${datasets[selectedDataset]?.name || "dataset"}…` : "Select a demo dataset"}
                        </span>
                        <ChevronDown size={16} className={`text-muted transition-transform ${showDatasets ? "rotate-180" : ""}`} />
                    </button>

                    {showDatasets && (
                        <div
                            id="demo-dataset-list"
                            role="listbox"
                            aria-label="Demo datasets"
                            className="absolute bottom-full left-0 right-0 z-20 mb-2 max-h-[60vh] overflow-y-auto rounded-xl border border-border bg-surface shadow-[var(--shadow)]"
                        >
                            {Object.entries(datasets).map(([id, config]) => (
                                <button
                                    key={id}
                                    role="option"
                                    aria-selected={selectedDataset === id}
                                    onClick={() => loadDemo(id)}
                                    disabled={isUploading}
                                    className="w-full border-b border-border-soft px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-2 disabled:opacity-50"
                                >
                                    <p className="text-sm font-medium text-fg">{config.name}</p>
                                    <p className="mt-0.5 text-xs text-faint">{config.description}</p>
                                    <div className="mt-2 flex gap-2">
                                        <span className="rounded-md bg-accent-soft/50 px-2 py-0.5 font-mono text-[11px] text-accent">
                                            {config.rows} rows
                                        </span>
                                        <span className="rounded-md bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-muted">
                                            {config.columns} cols
                                        </span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
