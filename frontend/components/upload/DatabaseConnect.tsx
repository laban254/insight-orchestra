"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Schema } from "@/lib/types";

interface DatabaseConnectProps {
    onConnectSuccess: (schema: Schema) => void;
}

export function DatabaseConnect({ onConnectSuccess }: DatabaseConnectProps) {
    const [type, setType] = useState("postgresql");
    const [connectionString, setConnectionString] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
            onConnectSuccess(result.schema);
        } catch (err: unknown) {
            setError(getErrorMessage(err));
        } finally {
            setIsConnecting(false);
        }
    };

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
