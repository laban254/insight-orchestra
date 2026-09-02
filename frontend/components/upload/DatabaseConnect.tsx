"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, FileDown, Loader2, Search, Table2 } from "lucide-react";
import { api } from "@/lib/api";
import { LocalDatabaseFile, Schema } from "@/lib/types";
import type { DatasetInfo } from "@/app/page";

interface DatabaseConnectProps {
    onDataReady: (datasetId: string, info: DatasetInfo) => void;
}

export function DatabaseConnect({ onDataReady }: DatabaseConnectProps) {
    const [type, setType] = useState("postgresql");
    const [connectionString, setConnectionString] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Set once /connectors/connect succeeds — presence of connectionId drives
    // whether we show the connection form or the table picker.
    const [connectionId, setConnectionId] = useState<string | null>(null);
    const [schema, setSchema] = useState<Schema | null>(null);
    const [loadingTable, setLoadingTable] = useState<string | null>(null);
    const [tableSearch, setTableSearch] = useState("");

    // SQLite/DuckDB are file-backed, and the backend runs in a container —
    // so only files inside the mounted uploads directory are reachable.
    // Listing them beats asking for a path that can never resolve.
    const isFileBacked = type === "sqlite" || type === "duckdb";
    const [localFiles, setLocalFiles] = useState<LocalDatabaseFile[] | null>(null);
    const [hostDirectory, setHostDirectory] = useState("./backend/uploads");

    useEffect(() => {
        if (!isFileBacked) return;
        let cancelled = false;
        void api
            .listLocalDatabaseFiles()
            .then((r) => {
                if (cancelled) return;
                setLocalFiles(r.files);
                setHostDirectory(r.host_directory);
            })
            .catch(() => {
                if (!cancelled) setLocalFiles([]);
            });
        return () => {
            cancelled = true;
        };
    }, [isFileBacked]);

    const getErrorMessage = (err: unknown) => {
        if (
            typeof err === "object" &&
            err !== null &&
            "response" in err &&
            typeof (err as { response?: unknown }).response === "object"
        ) {
            const response = (err as { response?: { data?: { detail?: string } } }).response;
            return response?.data?.detail ?? "Connection failed";
        }
        if (err instanceof Error) {
            return err.message;
        }
        return "Connection failed";
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsConnecting(true);

        try {
            const result = await api.connectDatabase({ type, connection_string: connectionString });
            setConnectionId(result.connection_id);
            setSchema(result.schema);
        } catch (err: unknown) {
            setError(getErrorMessage(err));
        } finally {
            setIsConnecting(false);
        }
    };

    const handleBack = () => {
        if (connectionId) void api.disconnectDatabase(connectionId).catch(() => {});
        setConnectionId(null);
        setSchema(null);
        setError(null);
        setTableSearch("");
    };

    const handleSelectTable = async (tableName: string) => {
        if (!connectionId) return;
        setError(null);
        setLoadingTable(tableName);

        try {
            const result = await api.loadTable({ connection_id: connectionId, table_name: tableName });
            onDataReady(result.dataset_id, {
                name: tableName,
                type: "database",
                rows: result.row_count,
                columns: result.column_count,
                description: `Table "${tableName}" from ${type} database`,
            });
        } catch (err: unknown) {
            setError(getErrorMessage(err));
        } finally {
            setLoadingTable(null);
        }
    };

    if (connectionId && schema) {
        const tables = Object.entries(schema);
        const query = tableSearch.trim().toLowerCase();
        const filteredTables = query ? tables.filter(([name]) => name.toLowerCase().includes(query)) : tables;

        return (
            <div className="w-full space-y-4">
                <button
                    onClick={handleBack}
                    className="flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-fg"
                >
                    <ChevronLeft size={14} /> Back
                </button>

                <div>
                    <p className="text-sm font-medium text-fg">Select a table to analyze</p>
                    <p className="mt-0.5 text-xs text-faint">
                        {query
                            ? `${filteredTables.length} of ${tables.length} tables match`
                            : `${tables.length} table${tables.length === 1 ? "" : "s"} found`}
                    </p>
                </div>

                {tables.length > 8 && (
                    <div className="relative">
                        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                        <input
                            type="text"
                            value={tableSearch}
                            onChange={(e) => setTableSearch(e.target.value)}
                            placeholder="Search tables…"
                            autoFocus
                            className="w-full rounded-lg border border-border bg-surface py-2.5 pl-9 pr-3 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                        />
                    </div>
                )}

                {error && (
                    <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{error}</div>
                )}

                {filteredTables.length === 0 ? (
                    <p className="py-6 text-center text-sm text-faint">No tables match &ldquo;{tableSearch}&rdquo;</p>
                ) : (
                    <div className="max-h-[50vh] space-y-1.5 overflow-y-auto">
                        {filteredTables.map(([tableName, columns]) => (
                            <button
                                key={tableName}
                                onClick={() => handleSelectTable(tableName)}
                                disabled={loadingTable !== null}
                                className="flex w-full items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <span className="flex items-center gap-2 text-sm font-medium text-fg">
                                    <Table2 size={14} className="text-accent" />
                                    {tableName}
                                </span>
                                <span className="flex items-center gap-2 font-mono text-[11px] text-faint">
                                    {columns.length} col{columns.length === 1 ? "" : "s"}
                                    {loadingTable === tableName && <Loader2 size={13} className="animate-spin text-accent" />}
                                </span>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="w-full">
            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Database type</label>
                    <select
                        value={type}
                        onChange={(e) => setType(e.target.value)}
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-fg outline-none transition-colors focus:border-accent/60"
                    >
                        <option value="postgresql">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="duckdb">DuckDB</option>
                        <option value="sqlite">SQLite</option>
                    </select>
                </div>

                <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Connection string</label>
                    <input
                        type="text"
                        value={connectionString}
                        onChange={(e) => setConnectionString(e.target.value)}
                        placeholder={
                            type === "postgresql" ? "postgresql://user:pass@localhost:5432/db" :
                                type === "mysql" ? "mysql://user:pass@localhost:3306/db" :
                                    isFileBacked ? "Pick a file below, or paste a path inside the container" : ""
                        }
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 font-mono text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                        required
                    />
                    {isFileBacked && (
                        <div className="mt-2">
                            {localFiles === null ? (
                                <p className="text-xs text-faint">Looking for database files…</p>
                            ) : localFiles.length > 0 ? (
                                <>
                                    <p className="mb-1.5 text-xs text-faint">
                                        Found in <code className="rounded bg-surface-2 px-1 font-mono">{hostDirectory}</code>
                                    </p>
                                    <div className="max-h-40 space-y-1 overflow-y-auto">
                                        {localFiles.map((f) => (
                                            <button
                                                key={f.path}
                                                type="button"
                                                onClick={() => setConnectionString(f.path)}
                                                className={`flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition-colors ${
                                                    connectionString === f.path
                                                        ? "border-accent/60 bg-accent-soft/30 text-fg"
                                                        : "border-border bg-surface text-muted hover:border-accent/50"
                                                }`}
                                            >
                                                <FileDown size={13} className="shrink-0 text-accent" />
                                                <span className="truncate font-mono">{f.name}</span>
                                            </button>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <p className="text-xs text-faint">
                                    No database files found. Copy a <code className="rounded bg-surface-2 px-1 font-mono">.db</code>,{" "}
                                    <code className="rounded bg-surface-2 px-1 font-mono">.sqlite</code> or{" "}
                                    <code className="rounded bg-surface-2 px-1 font-mono">.duckdb</code> file into{" "}
                                    <code className="rounded bg-surface-2 px-1 font-mono">{hostDirectory}</code> — the backend runs in a
                                    container and can only reach files there.
                                </p>
                            )}
                        </div>
                    )}
                </div>

                {error && (
                    <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{error}</div>
                )}

                <button
                    type="submit"
                    disabled={isConnecting || !connectionString}
                    className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isConnecting ? "Connecting…" : "Connect"}
                </button>
            </form>
        </div>
    );
}
