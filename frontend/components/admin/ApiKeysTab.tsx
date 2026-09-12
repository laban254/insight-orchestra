"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound, Loader2, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/apiError";
import { useToast } from "@/lib/toast";
import type { ApiKey, ApiKeyWithSecret } from "@/lib/types";

function fmt(seconds: number | null): string {
    if (!seconds) return "—";
    return new Date(seconds * 1000).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

export function ApiKeysTab() {
    const toast = useToast();
    const [keys, setKeys] = useState<ApiKey[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [name, setName] = useState("");
    const [creating, setCreating] = useState(false);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [fresh, setFresh] = useState<ApiKeyWithSecret | null>(null);
    const [copied, setCopied] = useState(false);

    const load = useCallback(async () => {
        try {
            setKeys(await api.listApiKeys());
            setError(null);
        } catch (err) {
            setError(apiErrorMessage(err, "Could not load API keys."));
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const create = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim()) return;
        setCreating(true);
        try {
            const created = await api.createApiKey(name.trim());
            setFresh(created);
            setCopied(false);
            setName("");
            await load();
        } catch (err) {
            toast(apiErrorMessage(err, "Could not create the key."), "error");
        } finally {
            setCreating(false);
        }
    };

    const remove = async (k: ApiKey) => {
        if (!confirm(`Delete key "${k.name}"? Anything using it will stop working.`)) return;
        setBusyId(k.id);
        try {
            await api.deleteApiKey(k.id);
            if (fresh?.id === k.id) setFresh(null);
            await load();
        } catch (err) {
            toast(apiErrorMessage(err, "Delete failed."), "error");
        } finally {
            setBusyId(null);
        }
    };

    const copy = async () => {
        if (!fresh) return;
        try {
            await navigator.clipboard.writeText(fresh.key);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            toast("Couldn't copy — select and copy it manually.", "error");
        }
    };

    if (error) return <p className="text-sm text-red-400">{error}</p>;

    return (
        <div className="space-y-4">
            <p className="text-sm text-muted">
                Keys authenticate headless callers as you. Send them as{" "}
                <code className="rounded bg-surface-2 px-1 py-0.5 text-xs text-fg">Authorization: Bearer &lt;key&gt;</code>.
            </p>

            <form onSubmit={create} className="flex gap-2">
                <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Key name (e.g. CI pipeline)"
                    maxLength={200}
                    className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                />
                <button
                    type="submit"
                    disabled={creating || !name.trim()}
                    className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-60"
                >
                    {creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                    Create
                </button>
            </form>

            {fresh && (
                <div className="rounded-xl border border-accent/40 bg-accent/[0.06] p-4">
                    <p className="text-xs font-medium text-accent">
                        Copy this key now — it won&apos;t be shown again.
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                        <code className="flex-1 overflow-x-auto rounded-lg bg-surface px-3 py-2 font-mono text-xs text-fg">
                            {fresh.key}
                        </code>
                        <button
                            onClick={copy}
                            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-fg"
                            title="Copy"
                        >
                            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                        </button>
                    </div>
                </div>
            )}

            {!keys ? (
                <div className="flex items-center gap-2 py-8 text-sm text-faint">
                    <Loader2 size={15} className="animate-spin" /> Loading…
                </div>
            ) : keys.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-sm text-faint">
                    <KeyRound size={20} />
                    No API keys yet.
                </div>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-border">
                    <table className="w-full min-w-[560px] text-sm">
                        <thead>
                            <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-faint">
                                <th className="px-3 py-2.5 font-medium">Name</th>
                                <th className="px-3 py-2.5 font-medium">Prefix</th>
                                <th className="px-3 py-2.5 font-medium">Created</th>
                                <th className="px-3 py-2.5 font-medium">Last used</th>
                                <th className="px-3 py-2.5 font-medium">Expires</th>
                                <th className="px-3 py-2.5" />
                            </tr>
                        </thead>
                        <tbody>
                            {keys.map((k) => (
                                <tr key={k.id} className="border-b border-border-soft last:border-0">
                                    <td className="px-3 py-2.5 text-fg">{k.name}</td>
                                    <td className="px-3 py-2.5 font-mono text-xs text-muted">{k.display_prefix}…</td>
                                    <td className="px-3 py-2.5 text-faint">{fmt(k.created_at)}</td>
                                    <td className="px-3 py-2.5 text-faint">{fmt(k.last_used_at)}</td>
                                    <td className="px-3 py-2.5 text-faint">{fmt(k.expires_at)}</td>
                                    <td className="px-3 py-2.5 text-right">
                                        {busyId === k.id ? (
                                            <Loader2 size={14} className="ml-auto animate-spin text-faint" />
                                        ) : (
                                            <button
                                                onClick={() => remove(k)}
                                                title="Delete key"
                                                className="text-faint transition-colors hover:text-red-400"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
