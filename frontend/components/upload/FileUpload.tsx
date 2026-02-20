"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export function FileUpload({ onUploadSuccess }: { onUploadSuccess: (filePath: string) => void }) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
    }, []);

    const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            await uploadFile(e.target.files[0]);
        }
    };

    const uploadFile = async (file: File) => {
        setError(null);
        setIsUploading(true);
        try {
            const result = await api.uploadFile(file);
            onUploadSuccess(result.file_path);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || "Upload failed");
        } finally {
            setIsUploading(false);
        }
    };

    const loadDemo = async () => {
        setError(null);
        setIsUploading(true);
        try {
            const result = await api.loadDemoData();
            onUploadSuccess(result.file_path);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || "Failed to load demo");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full max-w-md mx-auto space-y-4">
            <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
        `}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    id="file-upload"
                    onChange={handleChange}
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                    <div className="space-y-2">
                        <div className="flex justify-center">
                            <span className="text-4xl text-gray-400">📄</span>
                        </div>
                        {isUploading ? (
                            <p className="text-blue-500 font-medium">Uploading...</p>
                        ) : (
                            <>
                                <p className="text-sm font-medium text-gray-700">Click to upload or drag and drop</p>
                                <p className="text-xs text-gray-500">CSV files only</p>
                            </>
                        )}
                    </div>
                </label>
            </div>

            {error && (
                <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
                    {error}
                </div>
            )}

            <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Don't have a dataset?</span>
                <button
                    onClick={loadDemo}
                    disabled={isUploading}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50"
                >
                    Use Demo Dataset
                </button>
            </div>
        </div>
    );
}
