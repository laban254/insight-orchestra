"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/apiError";
import { useToast } from "@/lib/toast";
import type { AuditEntry } from "@/lib/types";

function fmtTime(seconds: number): string {
    return new Date(seconds * 1000).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

const ACTION_TONE: Record<string, string> = {
    login: "text-emerald-400",
    logout: "text-muted",
    login_failed: "text-red-400",
};

export function AuditLogTab() {
    const toast = useToast();
    const [entries, setEntries] = useState<AuditEntry[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [limit, setLimit] = useState(200);
    const [refreshing, setRefreshing] = useState(false);
    const [downloading, setDownloading] = useState(false);

    const load = useCallback(async () => {
        setRefreshing(true);
        try {
            setEntries(await api.listAuditLog(limit));
            setError(null);
        } catch (err) {
            setError(apiErrorMessage(err, "Could not load the audit log."));
        } finally {
            setRefreshing(false);
        }
    }, [limit]);

    useEffect(() => {
        load();
    }, [load]);

    const download = async () => {
        setDownloading(true);
        try {
            const blob = await api.downloadAuditLog();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "audit-log.jsonl";
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            toast(apiErrorMessage(err, "Export failed."), "error");
        } finally {
            setDownloading(false);
        }
    };

    if (error) return <p className="text-sm text-red-400">{error}</p>;

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-fg outline-none"
                    >
                        <option value={50}>Last 50</option>
                        <option value={200}>Last 200</option>
                        <option value={1000}>Last 1000</option>
                    </select>
                    <button
                        onClick={load}
                        disabled={refreshing}
                        className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-muted transition-colors hover:text-fg disabled:opacity-60"
                    >
                        <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} /> Refresh
                    </button>
                </div>
                <button
                    onClick={download}
                    disabled={downloading}
                    className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-muted transition-colors hover:text-fg disabled:opacity-60"
                >
                    {downloading ? (
                        <Loader2 size={13} className="animate-spin" />
                    ) : (
                        <Download size={13} />
                    )}
                    Export JSONL
                </button>
            </div>

            {!entries ? (
                <div className="flex items-center gap-2 py-8 text-sm text-faint">
                    <Loader2 size={15} className="animate-spin" /> Loading…
                </div>
            ) : entries.length === 0 ? (
                <p className="py-10 text-center text-sm text-faint">No audit entries yet.</p>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-border">
                    <table className="w-full min-w-[720px] text-sm">
                        <thead>
                            <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-faint">
                                <th className="px-3 py-2.5 font-medium">Time</th>
                                <th className="px-3 py-2.5 font-medium">Actor</th>
                                <th className="px-3 py-2.5 font-medium">Action</th>
                                <th className="px-3 py-2.5 font-medium">Resource</th>
                                <th className="px-3 py-2.5 font-medium">IP</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((e) => (
                                <tr key={e.id} className="border-b border-border-soft last:border-0 align-top">
                                    <td className="whitespace-nowrap px-3 py-2.5 text-faint">{fmtTime(e.timestamp)}</td>
                                    <td className="px-3 py-2.5 text-muted">{e.actor_email ?? "—"}</td>
                                    <td className={`px-3 py-2.5 font-medium ${ACTION_TONE[e.action] ?? "text-fg"}`}>
                                        {e.action}
                                    </td>
                                    <td className="px-3 py-2.5 font-mono text-xs text-muted">
                                        {e.resource ?? "—"}
                                        {e.detail && (
                                            <span className="block text-[11px] text-faint">
                                                {JSON.stringify(e.detail)}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-3 py-2.5 font-mono text-xs text-faint">{e.ip_address ?? "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
