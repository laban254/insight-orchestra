"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Eye, EyeOff, KeyRound, Loader2, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/apiError";
import { AuthShowcase } from "@/components/ui/AuthShowcase";
import { AuthBackground } from "@/components/ui/AuthBackground";
import { LogoMark } from "@/components/ui/Logo";
import { GithubMark } from "@/components/ui/GithubMark";

// Same field treatment as the sign-in page — see login/page.tsx.
const INPUT =
    "w-full rounded-lg border border-[#26324a] bg-[#121b29] px-4 py-2.5 text-[15px] leading-6 text-white outline-none transition-colors placeholder:text-[#7c8a9e] focus:border-accent focus:ring-2 focus:ring-accent/25";

const LINK =
    "font-medium text-accent underline decoration-accent/40 underline-offset-4 transition-colors hover:decoration-accent";

/** The marketing site hosts the public terms; there's no in-app terms page. */
const TERMS_URL = "https://marketing-insight-orchestra.vercel.app";
const WEBSITE_URL = TERMS_URL;
const GITHUB_URL = "https://github.com/laban254/insight-orchestra";

/**
 * Sign-up page — the mirror of the sign-in screen. Email + password only (OAuth
 * comes later); new accounts are created as `member` and signed in immediately.
 * Shown only when the server reports sign-up is enabled; otherwise the visitor
 * is sent to /login.
 */
export default function SignupPage() {
    const { authEnabled, signupEnabled, oidcConfigured, user, loading, register, oidcLoginUrl } = useAuth();
    const router = useRouter();
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [agreed, setAgreed] = useState(false);
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
            await register(`${firstName} ${lastName}`.trim(), email, password);
            router.replace("/");
        } catch (err) {
            setError(apiErrorMessage(err, "Could not create your account. Please try again."));
            setSubmitting(false);
        }
    };

    if (loading || !authEnabled || !signupEnabled || user) {
        return (
            <main className="dark grid min-h-screen place-items-center bg-[#020713] [color-scheme:dark]">
                <Loader2 className="animate-spin text-accent" size={28} aria-label="Loading" />
            </main>
        );
    }

    return (
        <main className="dark relative flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-10 [color-scheme:dark] sm:px-6">
            <AuthBackground />
            <div className="w-full max-w-[1120px] overflow-hidden rounded-[20px] border border-white/[0.08] bg-[#101827] shadow-[0_50px_140px_-50px_rgba(0,0,0,0.95)]">
                <div className="grid lg:min-h-[680px] lg:grid-cols-[0.95fr_1.05fr]">
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
                                Create an account
                            </h1>
                            <p className="mt-3 text-[15px] text-[#98a6b8]">
                                Already have an account? <Link href="/login" className={LINK}>Log in</Link>
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

                                <div className="grid grid-cols-2 gap-3">
                                    <input
                                        id="firstName"
                                        name="firstName"
                                        type="text"
                                        value={firstName}
                                        onChange={(e) => setFirstName(e.target.value)}
                                        placeholder="First name"
                                        aria-label="First name"
                                        autoComplete="given-name"
                                        required
                                        maxLength={100}
                                        autoFocus
                                        aria-invalid={error ? true : undefined}
                                        className={INPUT}
                                    />
                                    <input
                                        id="lastName"
                                        name="lastName"
                                        type="text"
                                        value={lastName}
                                        onChange={(e) => setLastName(e.target.value)}
                                        placeholder="Last name"
                                        aria-label="Last name"
                                        autoComplete="family-name"
                                        maxLength={100}
                                        aria-invalid={error ? true : undefined}
                                        className={INPUT}
                                    />
                                </div>

                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="Email"
                                    aria-label="Email"
                                    autoComplete="email"
                                    required
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
                                        placeholder="Enter your password"
                                        aria-label="Password"
                                        autoComplete="new-password"
                                        required
                                        minLength={8}
                                        maxLength={200}
                                        aria-invalid={error ? true : undefined}
                                        className={`${INPUT} pr-12`}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword((v) => !v)}
                                        aria-label={showPassword ? "Hide password" : "Show password"}
                                        aria-pressed={showPassword}
                                        className="absolute right-2 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-md text-[#7c8a9e] transition-colors hover:text-white"
                                    >
                                        {showPassword ? (
                                            <EyeOff size={16} aria-hidden="true" />
                                        ) : (
                                            <Eye size={16} aria-hidden="true" />
                                        )}
                                    </button>
                                </div>

                                <label className="flex items-center gap-2.5 pt-1 text-[13px] text-[#98a6b8]">
                                    <input
                                        type="checkbox"
                                        checked={agreed}
                                        onChange={(e) => setAgreed(e.target.checked)}
                                        required
                                        className="h-4 w-4 shrink-0 accent-[var(--accent)]"
                                    />
                                    <span>
                                        I agree to the{" "}
                                        <a href={TERMS_URL} className={LINK}>
                                            Terms &amp; Conditions
                                        </a>
                                    </span>
                                </label>

                                <button
                                    type="submit"
                                    disabled={submitting || !agreed}
                                    className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[linear-gradient(90deg,#00dffd,#b085ff)] text-[15px] font-semibold text-white shadow-[0_10px_30px_-10px_rgba(176,133,255,0.7)] transition-[filter] hover:brightness-110 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/40 disabled:opacity-60"
                                >
                                    {submitting ? (
                                        <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                                    ) : (
                                        <UserPlus size={16} aria-hidden="true" />
                                    )}
                                    {submitting ? "Creating account…" : "Create account"}
                                </button>
                            </form>

                            {oidcConfigured && (
                                <>
                                    <div className="my-6 flex items-center gap-3 text-xs text-[#7c8a9e]">
                                        <span className="h-px flex-1 bg-[#26324a]" />
                                        Or register with
                                        <span className="h-px flex-1 bg-[#26324a]" />
                                    </div>
                                    <a
                                        href={oidcLoginUrl}
                                        className="flex h-12 w-full items-center justify-center gap-2 rounded-lg border border-[#26324a] text-[15px] font-medium text-white transition-colors hover:border-accent/50 hover:bg-white/[0.04]"
                                    >
                                        <KeyRound size={16} className="text-[#98a6b8]" aria-hidden="true" />
                                        Continue with SSO
                                    </a>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-6 text-sm text-[#98a6b8]">
                <a
                    href={WEBSITE_URL}
                    className="inline-flex items-center gap-1.5 transition-colors hover:text-white"
                >
                    <ArrowLeft size={14} aria-hidden="true" />
                    Back to website
                </a>
                <a
                    href={GITHUB_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 transition-colors hover:text-white"
                >
                    <GithubMark size={16} />
                    GitHub
                </a>
            </div>
        </main>
    );
}
