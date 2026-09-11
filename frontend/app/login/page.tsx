"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, LogIn, MessageSquare, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { Logo } from "@/components/ui/Logo";
import { LoginArt } from "@/components/ui/LoginArt";

const HIGHLIGHTS = [
    {
        Icon: Sparkles,
        tone: "text-accent bg-accent/15",
        title: "A 4-agent pipeline",
        body: "Cleans, hypothesizes, debates, and charts your data automatically",
    },
    {
        Icon: MessageSquare,
        tone: "text-accent-2 bg-accent-2/15",
        title: "Ask follow-up questions",
        body: "Natural-language queries against your dataset or database",
    },
    {
        Icon: ShieldCheck,
        tone: "text-success bg-success/15",
        title: "Self-hosted",
        body: "Your data never leaves your machine",
    },
];

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
        <main className="grid min-h-screen bg-bg lg:grid-cols-2">
            {/* Branding panel — what you're signing into. Desktop only; the
                form panel carries a compact version of this on small screens. */}
            <div className="relative hidden overflow-hidden border-border bg-surface lg:flex lg:flex-col lg:justify-between lg:border-r lg:p-12">
                <div
                    aria-hidden
                    className="pointer-events-none absolute inset-0 opacity-40"
                    style={{
                        backgroundImage: "radial-gradient(var(--border) 1px, transparent 1px)",
                        backgroundSize: "22px 22px",
                    }}
                />
                <div
                    aria-hidden
                    className="animate-drift pointer-events-none absolute -left-20 -top-20 h-96 w-96 rounded-full bg-accent/20 blur-3xl"
                />
                <div
                    aria-hidden
                    className="animate-drift pointer-events-none absolute -bottom-28 -right-12 h-80 w-80 rounded-full bg-accent-2/10 blur-3xl"
                    style={{ animationDelay: "-8s" }}
                />
                <div
                    aria-hidden
                    className="animate-drift pointer-events-none absolute right-1/3 top-1/4 h-64 w-64 rounded-full bg-success/10 blur-3xl"
                    style={{ animationDelay: "-4s" }}
                />

                <div className="relative z-10 flex items-center gap-3">
                    <Logo size={9} />
                    <span className="text-base font-bold tracking-tight text-fg">Insight Orchestra</span>
                </div>

                <div className="relative z-10 max-w-md">
                    <div className="-ml-2 h-40 w-[calc(100%+2rem)] sm:h-48">
                        <LoginArt />
                    </div>
                    <h2 className="mt-2 text-3xl font-bold leading-tight tracking-tight text-fg">
                        Upload data. Ask questions. Get answers — in plain English.
                    </h2>
                    <ul className="mt-7 space-y-4">
                        {HIGHLIGHTS.map(({ Icon, tone, title, body }) => (
                            <li key={title} className="flex gap-3.5">
                                <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${tone}`}>
                                    <Icon size={17} />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-fg">{title}</p>
                                    <p className="mt-0.5 text-xs leading-relaxed text-muted">{body}</p>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>

                <p className="relative z-10 text-xs text-faint">Open source · Apache 2.0</p>
            </div>

            {/* Form panel */}
            <div className="flex min-h-screen flex-col items-center justify-center p-6">
                <div className="w-full max-w-sm">
                    <div className="mb-8 flex flex-col items-center gap-3 text-center lg:hidden">
                        <Logo size={11} />
                        <h1 className="text-xl font-bold tracking-tight text-fg">Insight Orchestra</h1>
                    </div>

                    <div className="mb-6">
                        <h2 className="text-xl font-semibold text-fg">Welcome back</h2>
                        <p className="mt-1.5 text-sm text-muted">Sign in with your account email and password.</p>
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
            </div>
        </main>
    );
}
