"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, KeyRound, Loader2, ScrollText, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { UsersTab } from "@/components/admin/UsersTab";
import { ApiKeysTab } from "@/components/admin/ApiKeysTab";
import { AuditLogTab } from "@/components/admin/AuditLogTab";

type TabId = "users" | "keys" | "audit";

const TABS: { id: TabId; label: string; Icon: typeof Users }[] = [
    { id: "users", label: "Users", Icon: Users },
    { id: "keys", label: "API Keys", Icon: KeyRound },
    { id: "audit", label: "Audit Log", Icon: ScrollText },
];

export default function AdminPage() {
    const { authEnabled, user, loading } = useAuth();
    const router = useRouter();
    const [tab, setTab] = useState<TabId>("users");

    const forbidden = !loading && (!authEnabled || !user || user.role !== "admin");

    useEffect(() => {
        if (forbidden) router.replace("/");
    }, [forbidden, router]);

    if (loading || forbidden) {
        return (
            <main className="grid min-h-screen place-items-center bg-bg">
                <Loader2 className="animate-spin text-accent" size={28} />
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-bg">
            <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
                <Link
                    href="/"
                    className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-fg"
                >
                    <ArrowLeft size={15} /> Back to workspace
                </Link>

                <h1 className="text-xl font-semibold text-fg">Admin</h1>
                <p className="mt-1 text-sm text-muted">Accounts, API keys, and the audit trail.</p>

                <div className="mt-6 flex gap-1 border-b border-border">
                    {TABS.map(({ id, label, Icon }) => (
                        <button
                            key={id}
                            onClick={() => setTab(id)}
                            className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
                                tab === id
                                    ? "border-accent text-accent"
                                    : "border-transparent text-muted hover:text-fg"
                            }`}
                        >
                            <Icon size={15} /> {label}
                        </button>
                    ))}
                </div>

                <div className="mt-6">
                    {tab === "users" && <UsersTab />}
                    {tab === "keys" && <ApiKeysTab />}
                    {tab === "audit" && <AuditLogTab />}
                </div>
            </div>
        </main>
    );
}
