"use client";

import { useState } from "react";
import { Download, FileCode, FileText, Table } from "lucide-react";
import { api } from "@/lib/api";

interface ExportPanelProps {
    sessionId: string;
}

export function ExportPanel({ sessionId }: ExportPanelProps) {
    const [isExporting, setIsExporting] = useState<string | null>(null);

    const handleExport = async (format: "html" | "markdown" | "csv") => {
        setIsExporting(format);
        try {
            const url = api.getExportUrl(sessionId, format);
            // Create a temporary link to download the file
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", `insight-orchestra-report.${format}`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error("Export failed:", error);
            alert("Failed to export report. See console for details.");
        } finally {
            setIsExporting(null);
        }
    };

    return (
        <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-2">
                Export Report:
            </span>

            <button
                onClick={() => handleExport("html")}
                disabled={!!isExporting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-50 text-blue-600 rounded-md hover:bg-blue-100 disabled:opacity-50 transition-colors"
            >
                {isExporting === "html" ? <span className="animate-pulse">...</span> : <FileCode size={14} />}
                HTML
            </button>

            <button
                onClick={() => handleExport("markdown")}
                disabled={!!isExporting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
                {isExporting === "markdown" ? <span className="animate-pulse">...</span> : <FileText size={14} />}
                Markdown
            </button>

            <button
                onClick={() => handleExport("csv")}
                disabled={!!isExporting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-green-50 text-green-700 rounded-md hover:bg-green-100 disabled:opacity-50 transition-colors"
            >
                {isExporting === "csv" ? <span className="animate-pulse">...</span> : <Table size={14} />}
                Data (CSV)
            </button>
        </div>
    );
}
