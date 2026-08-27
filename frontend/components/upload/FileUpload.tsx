"use client";

import { useState, useCallback } from "react";
import { UploadCloud, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { ParseAssumptions } from "@/lib/types";

interface UploadInfo {
    type: "uploaded" | "demo";
    name: string;
    rows: number | string;
    columns: number | string;
    description?: string;
    use_cases?: string[];
    assumptions?: ParseAssumptions;
}

export function FileUpload({
    onUploadSuccess,
}: {
    onUploadSuccess: (filePath: string, info: UploadInfo) => void;
}) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const getErrorMessage = (err: unknown, fallback: string) => {
        if (
            typeof err === "object" &&
            err !== null &&
            "response" in err &&
            typeof (err as { response?: unknown }).response === "object"
        ) {
            const response = (err as { response?: { data?: { detail?: string } } }).response;
            return response?.data?.detail ?? fallback;
        }
        if (err instanceof Error) {
            return err.message;
        }
        return fallback;
    };

    const uploadFile = useCallback(async (file: File) => {
        setError(null);
        setIsUploading(true);
        try {
            const result = await api.uploadFile(file);
            onUploadSuccess(result.file_path, {
                name: result.name || file.name,
                type: "uploaded",
                rows: result.rows,
                columns: result.columns,
                assumptions: result.assumptions,
            });
        } catch (err: unknown) {
            setError(getErrorMessage(err, "Upload failed"));
        } finally {
            setIsUploading(false);
        }
    }, [onUploadSuccess]);

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setIsDragging(true);
        } else if (e.type === "dragleave") {
            setIsDragging(false);
        }
    }, []);

    const handleDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            await uploadFile(e.dataTransfer.files[0]);
        }
    }, [uploadFile]);

    const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            await uploadFile(e.target.files[0]);
        }
    };

    const loadDemo = async () => {
        setError(null);
        setIsUploading(true);
        try {
            const result = await api.loadDemoData();
            onUploadSuccess(result.file_path, {
                name: result.dataset_name,
                type: "demo",
                rows: result.row_count,
                columns: result.column_count,
                description: result.description,
                use_cases: result.use_cases,
            });
        } catch (err: unknown) {
            setError(getErrorMessage(err, "Failed to load demo"));
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full space-y-4">
            <div
                className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                    isDragging ? "border-accent bg-accent-soft/30" : "border-border hover:border-accent/50"
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input type="file" accept=".csv" className="hidden" id="file-upload" onChange={handleChange} />
                <label htmlFor="file-upload" className="flex cursor-pointer flex-col items-center gap-2">
                    {isUploading ? (
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

            <div className="flex items-center justify-between">
                <span className="text-sm text-faint">Don&apos;t have a dataset?</span>
                <button
                    onClick={loadDemo}
                    disabled={isUploading}
                    className="text-sm font-medium text-accent transition-opacity hover:opacity-80 disabled:opacity-50"
                >
                    Use demo dataset
                </button>
            </div>
        </div>
    );
}
