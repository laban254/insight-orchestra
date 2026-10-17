"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Eye, EyeOff, KeyRound, Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { AuthBackdrop } from "@/components/ui/AuthBackdrop";
import { AuthVisual } from "@/components/ui/AuthVisual";
import { Logo } from "@/components/ui/Logo";

/**
 * Sign-in page.
 *
 * Always dark, on the marketing brand system: a navy field lit by
 * cyan/violet/fuchsia glows, a glass card, the brand mark and heading, and the
 * signature gradient on the primary action. On desktop a second panel shows
 * the real five-agent pipeline over a screenshot of the product, so the front
 * door explains what the thing does. The form itself stays conventional —
 * persistent labels, show/hide, Caps Lock hint, autofill-friendly inputs.
 */
export default function LoginPage() {
    const { authEnabled, oidcConfigured, signupEnabled, user, loading, login, oidcLoginUrl } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [capsLock, setCapsLock] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!loading && (!authEnabled || user)) router.replace("/");
    }, [loading, authEnabled, user, router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await login(email, password);
            router.replace("/");
        } catch (err) {
            // Keep the email so the user only has to retype the password.
            setError(apiErrorMessage(err, "Incorrect email or password. Please try again."));
            setSubmitting(false);
        }
    };

    if (loading || !authEnabled || user) {
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
                            Welcome back
                        </h1>
                        <p className="mt-2 text-sm text-muted">
                            Sign in to your Insight Orchestra workspace.
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
                                        autoComplete="username"
                                        autoFocus
                                        required
                                        aria-invalid={error ? true : undefined}
                                        className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                                    />
                                </div>

                                <div>
                                    <div className="mb-1.5 flex items-center justify-between gap-2">
                                        <label htmlFor="password" className="text-sm font-medium text-fg">
                                            Password
                                        </label>
                                        {capsLock && (
                                            <span className="text-[11px] font-medium text-warning">Caps Lock is on</span>
                                        )}
                                    </div>
                                    <div className="relative">
                                        <input
                                            id="password"
                                            name="password"
                                            type={showPassword ? "text" : "password"}
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                                            onKeyDown={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                                            placeholder="••••••••"
                                            autoComplete="current-password"
                                            required
                                            aria-invalid={error ? true : undefined}
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
                                </div>

                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:opacity-90 disabled:opacity-60"
                                >
                                    {submitting ? (
                                        <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                                    ) : (
                                        <LogIn size={15} aria-hidden="true" />
                                    )}
                                    {submitting ? "Signing in…" : "Sign in"}
                                </button>
                            </form>

                            {oidcConfigured && (
                                <>
                                    <div className="my-5 flex items-center gap-3 text-xs text-faint">
                                        <div className="h-px flex-1 bg-border" />
                                        or
                                        <div className="h-px flex-1 bg-border" />
                                    </div>
                                    <a
                                        href={oidcLoginUrl}
                                        className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 text-sm font-medium text-fg transition-colors hover:bg-surface-2"
                                    >
                                        <KeyRound size={15} className="text-muted" aria-hidden="true" />
                                        Continue with SSO
                                    </a>
                                </>
                            )}

                            {signupEnabled && (
                                <p className="mt-6 border-t border-border-soft pt-5 text-center text-sm text-muted">
                                    Don&apos;t have an account?{" "}
                                    <Link
                                        href="/signup"
                                        className="font-medium text-accent underline-offset-2 hover:underline"
                                    >
                                        Sign up
                                    </Link>
                                </p>
                            )}
                        </div>

                    <div className="rounded-2xl border border-border bg-surface p-6 shadow-[var(--shadow)]">
                        <form onSubmit={handleSubmit} className="space-y-3">
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@company.com"
                                aria-label="Email"
                                autoComplete="username"
                                required
                                autoFocus
                                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                            />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Password"
                                aria-label="Password"
                                autoComplete="current-password"
                                required
                                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none transition-colors placeholder:text-faint focus:border-accent/60"
                            />
                            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
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

                {/* ── Proof panel ──────────────────────────────────────── */}
                <AuthVisual />
            </div>
        </main>
    );
}
