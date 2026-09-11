"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, LogIn } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { Logo } from "@/components/ui/Logo";

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
            setError(apiErrorMessage(err, "Sign-in failed."));
        } finally {
            setSubmitting(false);
        }
    };

    // Still resolving, or auth is off / already signed in (the effect above
    // is redirecting) — show a spinner rather than flashing the form.
    if (loading || !authEnabled || user) {
        return (
            <main className="grid min-h-screen place-items-center bg-bg">
                <Loader2 className="animate-spin text-accent" size={28} />
            </main>
        );
    }

    return (
        <main className="grid min-h-screen place-items-center bg-bg p-6">
            <div className="w-full max-w-sm">
                <div className="mb-8 flex flex-col items-center text-center">
                    <div className="mb-5">
                        <Logo size={12} />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight text-fg">Insight Orchestra</h1>
                    <p className="mt-2 text-sm text-muted">Sign in with your account email and password.</p>
                </div>

                <div className="rounded-2xl border border-border bg-surface p-6 shadow-[var(--shadow)]">
                    <form onSubmit={handleSubmit} className="space-y-3">
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="you@company.com"
                            required
                            autoFocus
                            className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                        />
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Password"
                            required
                            className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                        />
                        {error && <p className="text-sm text-danger">{error}</p>}
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
                                className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface-2 px-4 py-2.5 text-sm font-medium text-fg transition-colors hover:bg-surface-3"
                            >
                                Continue with SSO
                            </a>
                        </>
                    )}
                </div>
            </div>
        </main>
    );
}
