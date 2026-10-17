"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Eye, EyeOff, KeyRound, Loader2, LogIn } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { AuthShowcase } from "@/components/ui/AuthShowcase";
import { LogoMark } from "@/components/ui/Logo";

// Dark filled field on the card; focus picks up the app's primary (`--accent`).
// Placeholder-as-label — each input still carries an `aria-label`.
const INPUT =
    "w-full rounded-lg border border-[#2c2b34] bg-[#1e1d25] px-4 py-2.5 text-[15px] leading-6 text-white outline-none transition-colors placeholder:text-[#6f6c79] focus:border-accent focus:ring-2 focus:ring-accent/25";

const LINK =
    "font-medium text-accent underline decoration-accent/40 underline-offset-4 transition-colors hover:decoration-accent";

/** Sign-in page — a dark card split into a product showcase and the form. */
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
        // Auth off, or already signed in — nothing to do here.
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
            <main className="dark grid min-h-screen place-items-center bg-[#0b0a0e] [color-scheme:dark]">
                <Loader2 className="animate-spin text-accent" size={28} aria-label="Loading" />
            </main>
        );
    }

    return (
        <main className="dark grid min-h-screen place-items-center bg-[#0b0a0e] px-4 py-10 [color-scheme:dark] sm:px-6">
            <div className="w-full max-w-[1000px] overflow-hidden rounded-[20px] border border-white/[0.08] bg-[#16151c] shadow-[0_50px_140px_-50px_rgba(0,0,0,0.95)]">
                <div className="grid lg:min-h-[620px] lg:grid-cols-[0.92fr_1.08fr]">
                    <AuthShowcase />

                    <div className="px-6 py-10 sm:px-10 lg:px-14 lg:py-14">
                        <div className="mx-auto w-full max-w-[400px]">
                            <div className="mb-8 flex items-center justify-center gap-2 lg:hidden">
                                <LogoMark size={26} className="text-accent" />
                                <span className="font-heading text-base font-semibold text-white">
                                    Insight Orchestra
                                </span>
                            </div>

                            <h1 className="font-heading text-[34px] font-semibold leading-tight tracking-tight text-white sm:text-[38px]">
                                Sign in
                            </h1>
                            <p className="mt-3 text-[15px] text-[#9a96a6]">
                                {signupEnabled ? (
                                    <>
                                        New to Insight Orchestra? <Link href="/signup" className={LINK}>Create an account</Link>
                                    </>
                                ) : (
                                    "Sign in to your Insight Orchestra workspace."
                                )}
                            </p>

                            <form onSubmit={handleSubmit} className="mt-8 space-y-3">
                                {error && (
                                    <div
                                        role="alert"
                                        className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3.5 py-3 text-sm text-danger"
                                    >
                                        <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                                        <span>{error}</span>
                                    </div>
                                )}

                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="Email"
                                    aria-label="Email"
                                    autoComplete="username"
                                    required
                                    autoFocus
                                    aria-invalid={error ? true : undefined}
                                    className={INPUT}
                                />

                                <div className="relative">
                                    <input
                                        id="password"
                                        name="password"
                                        type={showPassword ? "text" : "password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                                        onKeyDown={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                                        placeholder="Enter your password"
                                        aria-label="Password"
                                        autoComplete="current-password"
                                        required
                                        aria-invalid={error ? true : undefined}
                                        className={`${INPUT} pr-12`}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword((v) => !v)}
                                        aria-label={showPassword ? "Hide password" : "Show password"}
                                        aria-pressed={showPassword}
                                        className="absolute right-2 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-md text-[#6f6c79] transition-colors hover:text-white"
                                    >
                                        {showPassword ? (
                                            <EyeOff size={16} aria-hidden="true" />
                                        ) : (
                                            <Eye size={16} aria-hidden="true" />
                                        )}
                                    </button>
                                </div>
                                {capsLock && (
                                    <p className="text-[12px] font-medium text-warning">Caps Lock is on</p>
                                )}

                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-accent text-[15px] font-semibold text-accent-fg transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/30 disabled:opacity-60"
                                >
                                    {submitting ? (
                                        <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                                    ) : (
                                        <LogIn size={16} aria-hidden="true" />
                                    )}
                                    {submitting ? "Signing in…" : "Sign in"}
                                </button>
                            </form>

                            {oidcConfigured && (
                                <>
                                    <div className="my-6 flex items-center gap-3 text-xs text-[#6f6c79]">
                                        <span className="h-px flex-1 bg-[#2c2b34]" />
                                        Or sign in with
                                        <span className="h-px flex-1 bg-[#2c2b34]" />
                                    </div>
                                    <a
                                        href={oidcLoginUrl}
                                        className="flex h-12 w-full items-center justify-center gap-2 rounded-lg border border-[#2c2b34] text-[15px] font-medium text-white transition-colors hover:border-accent/50 hover:bg-white/[0.04]"
                                    >
                                        <KeyRound size={16} className="text-[#9a96a6]" aria-hidden="true" />
                                        Continue with SSO
                                    </a>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
}
