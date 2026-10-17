import { Fragment } from "react";
import { ANALYSIS_FLOW, metaFor } from "@/lib/agents";

/**
 * The right-hand "proof" panel on the auth pages (desktop only): the real
 * five-agent pipeline lighting up in sequence, over the actual product
 * screenshot in a glass frame with a brand glow behind it.
 *
 * Truthful by construction — the agent names/colours come from the same
 * `lib/agents` metadata the product uses, and the screenshot is the real
 * workspace. The only motion is a gentle per-node pulse, staggered so it reads
 * as the pipeline running; `prefers-reduced-motion` collapses it (the keyframes
 * start and end fully lit, so nothing is left dimmed).
 */
export function AuthVisual() {
    return (
        <div className="relative hidden min-h-full flex-col items-center justify-center px-10 py-14 lg:flex">
            <div className="w-full max-w-[600px]">
                <p className="mb-5 text-center font-mono text-[11px] uppercase tracking-[0.22em] text-white/40">
                    Every analysis runs a pipeline of specialists
                </p>

                {/* The pipeline */}
                <div className="flex items-start">
                    {ANALYSIS_FLOW.map((id, i) => {
                        const meta = metaFor(id);
                        const Icon = meta.Icon;
                        return (
                            <Fragment key={id}>
                                <div className="flex w-[68px] flex-col items-center gap-2">
                                    <span
                                        className="grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur"
                                        style={{
                                            color: meta.color,
                                            boxShadow: `0 0 30px -12px ${meta.color}`,
                                            animation: `agent-light 7s ease-in-out ${i * 1.15}s infinite`,
                                        }}
                                    >
                                        <Icon size={18} aria-hidden="true" />
                                    </span>
                                    <span className="text-center text-[10px] font-medium leading-tight text-white/55">
                                        {meta.name}
                                    </span>
                                </div>
                                {i < ANALYSIS_FLOW.length - 1 && (
                                    <span
                                        aria-hidden="true"
                                        className="mt-[22px] h-px flex-1 bg-gradient-to-r from-white/25 via-white/10 to-white/25"
                                    />
                                )}
                            </Fragment>
                        );
                    })}
                </div>

                {/* The real product, in a glass frame */}
                <div className="relative mt-12">
                    <div
                        aria-hidden="true"
                        className="absolute -inset-8 -z-10 rounded-[3rem] blur-3xl"
                        style={{
                            background:
                                "radial-gradient(ellipse at 50% 25%, rgb(34 211 238 / 0.20), transparent 65%)",
                        }}
                    />
                    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] shadow-[0_40px_100px_-24px_rgba(0,0,0,0.75)] backdrop-blur">
                        <div className="flex items-center gap-2 border-b border-white/10 bg-black/20 px-4 py-2.5">
                            <div className="flex gap-1.5">
                                <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
                                <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
                                <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
                            </div>
                            <div className="mx-auto flex h-6 max-w-md flex-1 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] px-3 font-mono text-[10px] text-white/45">
                                insight-orchestra · localhost:8501
                            </div>
                        </div>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src="/workspace.webp"
                            alt="The Insight Orchestra workspace — conversation on the left, charts on the live canvas"
                            className="block w-full"
                        />
                    </div>
                </div>

                <p className="mt-8 text-center text-sm text-white/55">
                    Your data, analyzed by a{" "}
                    <span className="font-medium text-fg">team of AI agents</span>.
                </p>
            </div>
        </div>
    );
}
