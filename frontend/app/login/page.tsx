"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, Loader2, LogIn } from "lucide-react";
import { useAuth } from "@/lib/auth";

function getErrorMessage(err: unknown): string {
    if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: unknown }).response === "object"
    ) {
        const response = (err as { response?: { data?: { detail?: string } } }).response;
        return response?.data?.detail ?? "Sign-in failed.";
    }
    return "Sign-in failed.";
}

export default function LoginPage() {
    const { authEnabled, oidcConfigured, user, loading, login, oidcLoginUrl } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Auth off, or already signed in — nothing to do here.
        if (!loading && (!authEnabled || user)) {
            router.replace("/");
        }
    }, [loading, authEnabled, user, router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await login(email, password);
            router.replace("/");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading || (!loading && (!authEnabled || user))) {
        return (
            <main className="grid min-h-screen place-items-center bg-bg">
                <Loader2 className="animate-spin text-accent" size={28} />
            </main>
        );
    }

    return (
        <main className="grid min-h-screen place-items-center bg-bg p-6">
            <div className="w-full max-w-sm">
                <div className="mx-auto mb-5 grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent">
                    <KeyRound size={22} />
                </div>
                <h1 className="text-center text-lg font-semibold text-fg">Sign in to Insight Orchestra</h1>
                <p className="mt-1.5 text-center text-sm text-muted">Use your account email and password.</p>

                <form onSubmit={handleSubmit} className="mt-6 space-y-3">
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@company.com"
                        required
                        autoFocus
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                    />
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Password"
                        required
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                    />
                    {error && <p className="text-sm text-red-400">{error}</p>}
                    <button
                        type="submit"
                        disabled={submitting}
                        className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-60"
                    >
                        {submitting ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
                        Sign in
                    </button>
                </form>

                {oidcConfigured && (
                    <>
                        <div className="my-4 flex items-center gap-3 text-xs text-faint">
                            <div className="h-px flex-1 bg-border" />
                            or
                            <div className="h-px flex-1 bg-border" />
                        </div>
                        <a
                            href={oidcLoginUrl}
                            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium text-fg transition-colors hover:bg-surface-2"
                        >
                            Continue with SSO
                        </a>
                    </>
                )}
            </div>
        </main>
    );
}
