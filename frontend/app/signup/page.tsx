"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Eye, EyeOff, Loader2, ShieldCheck, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { AuthBackdrop } from "@/components/ui/AuthBackdrop";
import { AuthVisual } from "@/components/ui/AuthVisual";
import { Logo } from "@/components/ui/Logo";

/**
 * Sign-up page — the mirror of the sign-in screen, same brand surface.
 * Email + password only (OAuth comes later); new accounts are created as
 * `member` and signed in immediately. Shown only when the server reports
 * sign-up is enabled; otherwise the visitor is sent to /login.
 */
export default function SignupPage() {
    const { authEnabled, signupEnabled, user, loading, register } = useAuth();
    const router = useRouter();
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (loading) return;
        // Auth off (single-tenant) → straight in. Signed in → straight in.
        // Auth on but sign-up disabled → the login page is the only door.
        if (!authEnabled || user) router.replace("/");
        else if (!signupEnabled) router.replace("/login");
    }, [loading, authEnabled, signupEnabled, user, router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await register(name, email, password);
            router.replace("/");
        } catch (err) {
            setError(apiErrorMessage(err, "Could not create your account. Please try again."));
            setSubmitting(false);
        }
    };

    if (loading || !authEnabled || !signupEnabled || user) {
        return (
            <main className="dark auth-glass grid min-h-screen place-items-center bg-bg [color-scheme:dark]">
                <Loader2 className="animate-spin text-accent" size={28} aria-label="Loading" />
            </main>
        );
    }

    return (
        <main className="dark auth-glass relative min-h-screen overflow-hidden bg-bg [color-scheme:dark]">
            <AuthBackdrop />

            <div className="relative z-10 grid min-h-screen lg:grid-cols-2">
                {/* ── Form ─────────────────────────────────────────────── */}
                <div className="flex items-center justify-center px-6 py-12 sm:px-10">
                    <div className="w-full max-w-[400px]">
                        <Logo size={12} />

                        <h1 className="mt-6 font-heading text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
                            Create your account
                        </h1>
                        <p className="mt-2 text-sm text-muted">
                            Start analysing your data in minutes.
                        </p>

                        <div className="mt-8 rounded-2xl border border-border bg-surface p-6 shadow-[var(--shadow)] backdrop-blur-2xl sm:p-7">
                            <form onSubmit={handleSubmit} className="space-y-4">
                                {error && (
                                    <div
                                        role="alert"
                                        className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger"
                                    >
                                        <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                                        <span>{error}</span>
                                    </div>
                                )}

                                <div>
                                    <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-fg">
                                        Name
                                    </label>
                                    <input
                                        id="name"
                                        name="name"
                                        type="text"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="Ada Lovelace"
                                        autoComplete="name"
                                        autoFocus
                                        required
                                        maxLength={200}
                                        aria-invalid={error ? true : undefined}
                                        className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                                    />
                                </div>

                                <div>
                                    <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-fg">
                                        Email
                                    </label>
                                    <input
                                        id="email"
                                        name="email"
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="you@company.com"
                                        autoComplete="email"
                                        required
                                        aria-invalid={error ? true : undefined}
                                        className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                                    />
                                </div>

                                <div>
                                    <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-fg">
                                        Password
                                    </label>
                                    <div className="relative">
                                        <input
                                            id="password"
                                            name="password"
                                            type={showPassword ? "text" : "password"}
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            placeholder="At least 8 characters"
                                            autoComplete="new-password"
                                            required
                                            minLength={8}
                                            maxLength={200}
                                            aria-invalid={error ? true : undefined}
                                            aria-describedby="password-hint"
                                            className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-3 pr-11 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword((v) => !v)}
                                            aria-label={showPassword ? "Hide password" : "Show password"}
                                            aria-pressed={showPassword}
                                            className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-faint transition-colors hover:text-fg"
                                        >
                                            {showPassword ? (
                                                <EyeOff size={15} aria-hidden="true" />
                                            ) : (
                                                <Eye size={15} aria-hidden="true" />
                                            )}
                                        </button>
                                    </div>
                                    <p id="password-hint" className="mt-1.5 text-[11px] text-faint">
                                        Use at least 8 characters.
                                    </p>
                                </div>

                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:opacity-90 disabled:opacity-60"
                                >
                                    {submitting ? (
                                        <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                                    ) : (
                                        <UserPlus size={15} aria-hidden="true" />
                                    )}
                                    {submitting ? "Creating account…" : "Create account"}
                                </button>
                            </form>

                            <p className="mt-6 border-t border-border-soft pt-5 text-center text-sm text-muted">
                                Already have an account?{" "}
                                <Link
                                    href="/login"
                                    className="font-medium text-accent underline-offset-2 hover:underline"
                                >
                                    Sign in
                                </Link>
                            </p>
                        </div>

                        <p className="mt-6 flex items-center gap-1.5 text-xs text-faint">
                            <ShieldCheck size={13} className="shrink-0 text-brand-cyan" aria-hidden="true" />
                            Self-hosted — your data never leaves your machine
                        </p>
                    </div>
                </div>

                {/* ── Proof panel ──────────────────────────────────────── */}
                <AuthVisual />
            </div>
        </main>
    );
}
