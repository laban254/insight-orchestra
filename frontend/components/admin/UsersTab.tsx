"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { Select } from "@/components/ui/Select";
import type { AdminUser, UserRole } from "@/lib/types";

const ROLES: UserRole[] = ["admin", "member", "viewer"];

function fmtDate(seconds: number): string {
    return new Date(seconds * 1000).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
    });
}

export function UsersTab() {
    const { user: me } = useAuth();
    const toast = useToast();
    const [users, setUsers] = useState<AdminUser[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [showAdd, setShowAdd] = useState(false);

    const load = useCallback(async () => {
        try {
            setUsers(await api.listUsers());
            setError(null);
        } catch (err) {
            setError(apiErrorMessage(err, "Could not load users."));
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const patch = async (id: string, data: { role?: UserRole; is_active?: boolean }) => {
        setBusyId(id);
        try {
            await api.updateUser(id, data);
            await load();
        } catch (err) {
            toast(apiErrorMessage(err, "Update failed."), "error");
        } finally {
            setBusyId(null);
        }
    };

    const remove = async (u: AdminUser) => {
        if (!confirm(`Delete ${u.email}? This cannot be undone.`)) return;
        setBusyId(u.id);
        try {
            await api.deleteUser(u.id);
            await load();
            toast(`Deleted ${u.email}`, "success");
        } catch (err) {
            toast(apiErrorMessage(err, "Delete failed."), "error");
        } finally {
            setBusyId(null);
        }
    };

    if (error) return <p className="text-sm text-red-400">{error}</p>;
    if (!users)
        return (
            <div className="flex items-center gap-2 py-10 text-sm text-faint">
                <Loader2 size={15} className="animate-spin" /> Loading users…
            </div>
        );

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted">
                    {users.length} account{users.length === 1 ? "" : "s"}
                </p>
                <button
                    onClick={() => setShowAdd((s) => !s)}
                    className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-muted transition-colors hover:text-fg"
                >
                    <Plus size={13} /> Add user
                </button>
            </div>

            {showAdd && (
                <AddUserForm
                    onCreated={async () => {
                        setShowAdd(false);
                        await load();
                    }}
                />
            )}

            <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[640px] text-sm">
                    <thead>
                        <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-faint">
                            <th className="px-3 py-2.5 font-medium">Email</th>
                            <th className="px-3 py-2.5 font-medium">Name</th>
                            <th className="px-3 py-2.5 font-medium">Role</th>
                            <th className="px-3 py-2.5 font-medium">Sign-in</th>
                            <th className="px-3 py-2.5 font-medium">Status</th>
                            <th className="px-3 py-2.5 font-medium">Added</th>
                            <th className="px-3 py-2.5" />
                        </tr>
                    </thead>
                    <tbody>
                        {users.map((u) => {
                            const isSelf = u.id === me?.id;
                            const busy = busyId === u.id;
                            return (
                                <tr key={u.id} className="border-b border-border-soft last:border-0">
                                    <td className="px-3 py-2.5 text-fg">
                                        {u.email}
                                        {isSelf && <span className="ml-1.5 text-[10px] text-faint">(you)</span>}
                                    </td>
                                    <td className="px-3 py-2.5 text-muted">{u.name}</td>
                                    <td className="px-3 py-2.5">
                                        <Select
                                            dense
                                            wrapperClassName="w-[7.5rem]"
                                            value={u.role}
                                            disabled={busy || isSelf}
                                            onChange={(e) => patch(u.id, { role: e.target.value as UserRole })}
                                        >
                                            {ROLES.map((r) => (
                                                <option key={r} value={r}>
                                                    {r}
                                                </option>
                                            ))}
                                        </Select>
                                    </td>
                                    <td className="px-3 py-2.5 text-muted">{u.auth_provider}</td>
                                    <td className="px-3 py-2.5">
                                        <button
                                            disabled={busy || isSelf}
                                            onClick={() => patch(u.id, { is_active: !u.is_active })}
                                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 ${
                                                u.is_active
                                                    ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                                                    : "bg-faint/15 text-faint hover:bg-faint/25"
                                            }`}
                                        >
                                            {u.is_active ? "active" : "inactive"}
                                        </button>
                                    </td>
                                    <td className="px-3 py-2.5 text-faint">{fmtDate(u.created_at)}</td>
                                    <td className="px-3 py-2.5 text-right">
                                        {busy ? (
                                            <Loader2 size={14} className="ml-auto animate-spin text-faint" />
                                        ) : (
                                            <button
                                                disabled={isSelf}
                                                onClick={() => remove(u)}
                                                title={isSelf ? "You can't delete your own account" : "Delete user"}
                                                className="text-faint transition-colors hover:text-red-400 disabled:opacity-30 disabled:hover:text-faint"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function AddUserForm({ onCreated }: { onCreated: () => void }) {
    const toast = useToast();
    const [email, setEmail] = useState("");
    const [name, setName] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState<UserRole>("member");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await api.createUser({ email, name, password, role });
            toast(`Created ${email}`, "success");
            onCreated();
        } catch (err) {
            setError(apiErrorMessage(err, "Could not create the user."));
        } finally {
            setSubmitting(false);
        }
    };

    const input =
        "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60";

    return (
        <form onSubmit={submit} className="rounded-xl border border-border bg-surface-2 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
                <input
                    type="email"
                    required
                    placeholder="email@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={input}
                />
                <input
                    type="text"
                    required
                    placeholder="Full name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className={input}
                />
                <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Temporary password (min 8 chars)"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={input}
                />
                <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                    {ROLES.map((r) => (
                        <option key={r} value={r}>
                            {r}
                        </option>
                    ))}
                </Select>
            </div>
            {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
            <button
                type="submit"
                disabled={submitting}
                className="mt-3 flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-60"
            >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                Create user
            </button>
        </form>
    );
}
