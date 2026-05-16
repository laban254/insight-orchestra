"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, FileSpreadsheet } from "lucide-react";

interface DataTableProps {
    columns: string[];
    data: Record<string, unknown>[];
    title?: string;
    rowCount?: number;
}

export function DataTable({ columns, data, title = "Dataset Preview", rowCount }: DataTableProps) {
    const [page, setPage] = useState(0);
    const rowsPerPage = 10;

    const totalPages = Math.ceil(data.length / rowsPerPage);
    const currentData = data.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

    if (!data || data.length === 0) return null;

    return (
        <div className="w-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden my-6">
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
                <div className="flex items-center gap-2 text-gray-700">
                    <FileSpreadsheet size={18} className="text-blue-600" />
                    <h3 className="font-medium text-sm">{title}</h3>
                    {rowCount && <span className="text-xs text-gray-400 font-monoml-2">({rowCount} rows)</span>}
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left text-gray-600">
                    <thead className="text-xs text-gray-700 uppercase bg-gray-50/50 sticky top-0">
                        <tr>
                            {columns.map(c => (
                                <th key={c} className="px-4 py-3 border-b font-semibold whitespace-nowrap">
                                    {c}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {currentData.map((row, i) => (
                            <tr key={i} className="border-b hover:bg-gray-50/50 transition-colors">
                                {columns.map(c => (
                                    <td key={`${i}-${c}`} className="px-4 py-2.5 max-w-xs truncate text-gray-700">
                                        {String(row[c] ?? "")}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/30">
                    <span className="text-xs text-gray-500">
                        Showing {page * rowsPerPage + 1} to {Math.min((page + 1) * rowsPerPage, data.length)} of {data.length} entries
                    </span>
                    <div className="flex gap-1">
                        <button
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                            disabled={page === 0}
                            className="p-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:hover:bg-white text-gray-600 focus:outline-none"
                        >
                            <ChevronLeft size={16} />
                        </button>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                            disabled={page >= totalPages - 1}
                            className="p-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:hover:bg-white text-gray-600 focus:outline-none"
                        >
                            <ChevronRight size={16} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
