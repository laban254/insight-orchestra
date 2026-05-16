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
        <div className="w-full max-w-md mx-auto bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg font-medium mb-4">Connect to Database</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Database Type</label>
                    <select
                        value={type}
                        onChange={(e) => setType(e.target.value)}
                        className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                    >
                        <option value="postgresql">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="duckdb">DuckDB</option>
                        <option value="sqlite">SQLite</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                        Connection String
                    </label>
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
                        className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                        required
                    />
                    <p className="mt-1 text-xs text-gray-500">
                        For SQLite and DuckDB, you can use <code>:memory:</code>
                    </p>
                </div>

                {error && (
                    <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={isConnecting || !connectionString}
                    className="w-full bg-blue-600 text-white rounded-md py-2 px-4 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    {isConnecting ? "Connecting..." : "Connect"}
                </button>
            </form>
        </div>
    );
}
