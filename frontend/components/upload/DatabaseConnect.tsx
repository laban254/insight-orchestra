"use client";

import { useState } from "react";
import { ChevronLeft, Loader2, Search, Table2 } from "lucide-react";
import { api } from "@/lib/api";
import { Schema } from "@/lib/types";
import type { DatasetInfo } from "@/app/page";

interface DatabaseConnectProps {
    onDataReady: (filePath: string, info: DatasetInfo) => void;
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
            onDataReady(result.file_path, {
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
                                    type === "sqlite" ? "/path/to/database.db" :
                                        type === "duckdb" ? "/path/to/database.duckdb or :memory:" : ""
                        }
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 font-mono text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                        required
                    />
                    <p className="mt-1.5 text-xs text-faint">
                        For SQLite and DuckDB you can use <code className="rounded bg-surface-2 px-1 font-mono text-accent">:memory:</code>
                    </p>
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
