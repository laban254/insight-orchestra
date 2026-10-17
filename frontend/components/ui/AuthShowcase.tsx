import { ShieldCheck } from "lucide-react";
import { ANALYSIS_FLOW, metaFor } from "@/lib/agents";
import { LogoMark } from "@/components/ui/Logo";

/**
 * The left-hand panel on the auth screens (desktop only): the brand mark and
 * the actual five-agent pipeline, drawn from the same `lib/agents` metadata the
 * product uses — so the front door shows the real thing, not a stock photo.
 * Hidden below `lg` (the form panel carries the brand mark on small screens).
 */
export function AuthShowcase() {
    return (
        <div className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[0.06] bg-[#0d1626] p-8 lg:flex xl:p-10">
            <div
                aria-hidden="true"
                className="pointer-events-none absolute -top-24 left-1/2 h-56 w-[130%] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl"
            />

            <span className="relative flex items-center gap-2 text-white">
                <LogoMark size={26} />
                <span className="font-heading text-[15px] font-semibold tracking-tight">
                    Insight Orchestra
                </span>
            </span>

            <div className="relative">
                <h2 className="font-heading text-[26px] font-semibold leading-[1.2] tracking-tight text-white xl:text-[28px]">
                    Five specialists.
                    <br />
                    One answer.
                </h2>
                <p className="mt-3 text-[13px] leading-relaxed text-[#9aa6be]">
                    Upload a dataset and a team of agents cleans it, forms hypotheses,
                    debates them, and charts what matters — then ask anything in plain
                    English.
                </p>

                <ul className="mt-7 space-y-3.5">
                    {ANALYSIS_FLOW.map((id) => {
                        const meta = metaFor(id);
                        const Icon = meta.Icon;
                        return (
                            <li key={id} className="flex items-center gap-3">
                                <span
                                    className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border"
                                    style={{
                                        color: meta.color,
                                        borderColor: `${meta.color}33`,
                                        backgroundColor: `${meta.color}14`,
                                        boxShadow: `0 0 22px -10px ${meta.color}`,
                                    }}
                                >
                                    <Icon size={16} aria-hidden="true" />
                                </span>
                                <span className="min-w-0">
                                    <span className="block text-[13px] font-medium text-white">
                                        {meta.name}
                                    </span>
                                    <span className="block text-[11px] leading-snug text-[#8b96ac]">
                                        {meta.description}
                                    </span>
                                </span>
                            </li>
                        );
                    })}
                </ul>
            </div>

            <p className="relative flex items-center gap-1.5 text-xs text-[#7c879c]">
                <ShieldCheck size={13} className="shrink-0 text-accent" aria-hidden="true" />
                Self-hosted — your data never leaves your machine
            </p>
        </div>
    );
}
