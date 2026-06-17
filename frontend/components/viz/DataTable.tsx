"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Table2 } from "lucide-react";

interface DataTableProps {
    columns: string[];
    data: Record<string, unknown>[];
    title?: string;
    rowsPerPage?: number;
}

export function DataTable({ columns, data, title = "Data preview", rowsPerPage = 8 }: DataTableProps) {
    const [page, setPage] = useState(0);

    if (!data || data.length === 0 || columns.length === 0) return null;

    const totalPages = Math.ceil(data.length / rowsPerPage);
    const current = data.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

    return (
        <div className="overflow-hidden rounded-xl border border-border bg-surface">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                <Table2 size={14} className="text-accent" />
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-faint">{title}</h3>
                <span className="ml-auto font-mono text-[11px] text-faint">{data.length} sample rows</span>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                    <thead>
                        <tr>
                            {columns.map((c) => (
                                <th
                                    key={c}
                                    className="whitespace-nowrap border-b border-border bg-surface-2 px-3 py-2 font-mono font-semibold text-muted"
                                >
                                    {c}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {current.map((row, i) => (
                            <tr key={i} className="transition-colors hover:bg-surface-2/60">
                                {columns.map((c) => (
                                    <td
                                        key={`${i}-${c}`}
                                        className="max-w-[220px] truncate border-b border-border-soft px-3 py-2 text-fg/90"
                                        title={String(row[c] ?? "")}
                                    >
                                        {String(row[c] ?? "—")}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-border px-4 py-2">
                    <span className="font-mono text-[11px] text-faint">
                        {page * rowsPerPage + 1}–{Math.min((page + 1) * rowsPerPage, data.length)} of {data.length}
                    </span>
                    <div className="flex gap-1">
                        <button
                            onClick={() => setPage((p) => Math.max(0, p - 1))}
                            disabled={page === 0}
                            className="grid h-7 w-7 place-items-center rounded-md border border-border text-muted transition-colors hover:text-fg disabled:opacity-40"
                        >
                            <ChevronLeft size={15} />
                        </button>
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                            disabled={page >= totalPages - 1}
                            className="grid h-7 w-7 place-items-center rounded-md border border-border text-muted transition-colors hover:text-fg disabled:opacity-40"
                        >
                            <ChevronRight size={15} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
