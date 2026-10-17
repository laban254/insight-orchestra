import { LogoMark } from "@/components/ui/Logo";

/**
 * Deterministic PRNG (mulberry32) so the artwork is identical on the server and
 * the client — same dots, same edges, no hydration mismatch.
 */
function mulberry32(seed: number) {
    let a = seed;
    return () => {
        a |= 0;
        a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

type Pt = { x: number; y: number };

/** A small constellation: scattered data points, each wired to its two nearest
 *  neighbours — the shape of data being pulled into an orchestrated graph. */
function buildGraph(count: number, seed: number) {
    const rand = mulberry32(seed);
    const pts: Pt[] = Array.from({ length: count }, () => ({
        x: 32 + rand() * 536,
        y: 70 + rand() * 470,
    }));
    const edges: [number, number][] = [];
    const seen = new Set<string>();
    pts.forEach((p, i) => {
        pts
            .map((q, j) => ({ j, d: (p.x - q.x) ** 2 + (p.y - q.y) ** 2 }))
            .filter((o) => o.j !== i)
            .sort((m, n) => m.d - n.d)
            .slice(0, 2)
            .forEach(({ j }) => {
                const key = i < j ? `${i}-${j}` : `${j}-${i}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    edges.push([i, j]);
                }
            });
    });
    return { pts, edges };
}

const GRAPH = buildGraph(24, 11);

/**
 * The left-hand panel on the auth screens (desktop only): a generated
 * "data-orchestration" artwork — a rising trend line under an agent
 * constellation — carrying the brand mark, a one-line pitch and carousel dots.
 * Pure SVG with one deterministic seed, so there's no image asset to ship and
 * it never goes stale. Decorative: hidden below `lg` and from assistive tech.
 */
export function AuthShowcase() {
    return (
        <div className="relative hidden overflow-hidden bg-[#07101d] lg:block">
            <svg
                viewBox="0 0 600 800"
                preserveAspectRatio="xMidYMid slice"
                className="absolute inset-0 h-full w-full"
                aria-hidden="true"
            >
                <defs>
                    <linearGradient id="io-edge" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" />
                        <stop offset="100%" stopColor="#a78bfa" />
                    </linearGradient>
                    <linearGradient id="io-area" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.34" />
                        <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
                    </linearGradient>
                    <radialGradient id="io-glow" cx="50%" cy="38%" r="62%">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.16" />
                        <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
                    </radialGradient>
                </defs>

                <rect width="600" height="800" fill="url(#io-glow)" />

                {/* data grid */}
                <g stroke="#ffffff" strokeOpacity="0.045">
                    {Array.from({ length: 13 }, (_, i) => (
                        <line key={`v${i}`} x1={i * 50} y1="0" x2={i * 50} y2="800" />
                    ))}
                    {Array.from({ length: 17 }, (_, i) => (
                        <line key={`h${i}`} x1="0" y1={i * 50} x2="600" y2={i * 50} />
                    ))}
                </g>

                {/* the constellation */}
                <g stroke="url(#io-edge)" strokeWidth="1" strokeOpacity="0.3">
                    {GRAPH.edges.map(([a, b], i) => (
                        <line key={i} x1={GRAPH.pts[a].x} y1={GRAPH.pts[a].y} x2={GRAPH.pts[b].x} y2={GRAPH.pts[b].y} />
                    ))}
                </g>
                {GRAPH.pts.map((p, i) =>
                    i % 5 === 0 ? (
                        <g key={i}>
                            <circle
                                cx={p.x}
                                cy={p.y}
                                r="8"
                                fill="#22d3ee"
                                fillOpacity="0.14"
                                className="auth-node-pulse"
                                style={{ animationDelay: `${(i % 4) * 0.7}s` }}
                            />
                            <circle cx={p.x} cy={p.y} r="3.2" fill="#22d3ee" />
                        </g>
                    ) : (
                        <circle key={i} cx={p.x} cy={p.y} r="1.8" fill="#a78bfa" fillOpacity="0.75" />
                    )
                )}

                {/* the payoff: a rising trend under the graph */}
                <path
                    d="M0,700 C110,690 150,620 250,628 C350,636 380,520 470,486 C530,463 566,448 600,432 L600,800 L0,800 Z"
                    fill="url(#io-area)"
                />
                <path
                    d="M0,700 C110,690 150,620 250,628 C350,636 380,520 470,486 C530,463 566,448 600,432"
                    fill="none"
                    stroke="#22d3ee"
                    strokeWidth="1.5"
                    strokeOpacity="0.55"
                />
            </svg>

            {/* Legibility wash for the overlaid content. */}
            <div
                aria-hidden="true"
                className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/35 to-black/25"
            />

            <div className="relative flex h-full flex-col justify-between p-8 xl:p-10">
                <span className="flex items-center gap-2 text-white">
                    <LogoMark size={26} />
                    <span className="font-heading text-[15px] font-semibold tracking-tight">
                        Insight Orchestra
                    </span>
                </span>

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
