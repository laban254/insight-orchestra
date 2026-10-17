import { ArrowRight } from "lucide-react";
import { LogoMark } from "@/components/ui/Logo";

/** The marketing site — the app's public front door, distinct from the app. */
const WEBSITE_URL = "https://marketing-insight-orchestra.vercel.app";

/**
 * The left-hand panel on the auth screens (desktop only): a full-bleed product
 * screenshot under a dark violet wash, carrying the brand mark, a link back to
 * the website, and the one-line pitch over carousel dots. Decorative, so it's
 * hidden below `lg` and from assistive tech (the form panel carries the same
 * brand mark on small screens).
 */
export function AuthShowcase() {
    return (
        <div className="relative hidden overflow-hidden lg:block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
                src="/workspace.webp"
                alt=""
                aria-hidden="true"
                className="absolute inset-0 h-full w-full object-cover"
            />
            <div aria-hidden="true" className="absolute inset-0 bg-[#432a8f]/45 mix-blend-multiply" />
            <div
                aria-hidden="true"
                className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/35 to-black/25"
            />

            <div className="relative flex h-full flex-col justify-between p-8 xl:p-10">
                <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-white">
                        <LogoMark size={26} />
                        <span className="font-heading text-[15px] font-semibold tracking-tight">
                            Insight Orchestra
                        </span>
                    </span>
                    <a
                        href={WEBSITE_URL}
                        className="inline-flex items-center gap-1.5 rounded-full border border-white/25 bg-white/10 px-3.5 py-1.5 text-xs font-medium text-white backdrop-blur transition-colors hover:bg-white/20"
                    >
                        Back to website <ArrowRight size={13} aria-hidden="true" />
                    </a>
                </div>

                <div>
                    <h2 className="font-heading text-[30px] font-semibold leading-[1.15] tracking-tight text-white">
                        Your data, analyzed
                        <br />
                        by a team of AI agents.
                    </h2>
                    <div className="mt-6 flex items-center gap-1.5" aria-hidden="true">
                        <span className="h-1 w-7 rounded-full bg-white" />
                        <span className="h-1 w-3 rounded-full bg-white/35" />
                        <span className="h-1 w-3 rounded-full bg-white/35" />
                    </div>
                </div>
            </div>
        </div>
    );
}
