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

/** Scattered data points, each wired to its two nearest neighbours. */
function buildGraph(count: number, seed: number, w: number, h: number) {
    const rand = mulberry32(seed);
    const pts: Pt[] = Array.from({ length: count }, () => ({
        x: 60 + rand() * (w - 120),
        y: 80 + rand() * (h * 0.62),
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

const GRAPH = buildGraph(34, 2026, 1440, 900);

/**
 * The full-page backdrop for the auth screens: a generated
 * "data-orchestration" artwork — a wired constellation over a rising trend —
 * dimmed behind a vignette so the card stays legible. Pure SVG from one seed:
 * no image to ship, crisp at any size, themed by the app accent.
 */
export function AuthBackground() {
    return (
        <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#070b14]">
            <svg
                viewBox="0 0 1440 900"
                preserveAspectRatio="xMidYMid slice"
                className="absolute inset-0 h-full w-full"
            >
                <defs>
                    <linearGradient id="bg-edge" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" />
                        <stop offset="55%" stopColor="#7c5cff" />
                        <stop offset="100%" stopColor="#e879f9" />
                    </linearGradient>
                    <linearGradient id="bg-area" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.22" />
                        <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
                    </linearGradient>
                    <radialGradient id="bg-glow" cx="50%" cy="34%" r="60%">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.1" />
                        <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
                    </radialGradient>
                </defs>

                <rect width="1440" height="900" fill="url(#bg-glow)" />

                <g stroke="#ffffff" strokeOpacity="0.04">
                    {Array.from({ length: 25 }, (_, i) => (
                        <line key={`v${i}`} x1={i * 60} y1="0" x2={i * 60} y2="900" />
                    ))}
                    {Array.from({ length: 16 }, (_, i) => (
                        <line key={`h${i}`} x1="0" y1={i * 60} x2="1440" y2={i * 60} />
                    ))}
                </g>

                <g stroke="url(#bg-edge)" strokeWidth="1" strokeOpacity="0.22">
                    {GRAPH.edges.map(([a, b], i) => (
                        <line
                            key={i}
                            x1={GRAPH.pts[a].x}
                            y1={GRAPH.pts[a].y}
                            x2={GRAPH.pts[b].x}
                            y2={GRAPH.pts[b].y}
                        />
                    ))}
                </g>
                {GRAPH.pts.map((p, i) =>
                    i % 6 === 0 ? (
                        <g key={i}>
                            <circle
                                cx={p.x}
                                cy={p.y}
                                r="7"
                                fill="#22d3ee"
                                fillOpacity="0.1"
                                className="auth-node-pulse"
                                style={{ animationDelay: `${(i % 5) * 0.6}s` }}
                            />
                            <circle cx={p.x} cy={p.y} r="2.6" fill="#22d3ee" fillOpacity="0.8" />
                        </g>
                    ) : (
                        <circle key={i} cx={p.x} cy={p.y} r="1.6" fill="#a78bfa" fillOpacity="0.5" />
                    )
                )}

                <path
                    d="M0,780 C240,760 420,640 700,650 C980,660 1100,470 1440,400 L1440,900 L0,900 Z"
                    fill="url(#bg-area)"
                />
                <path
                    d="M0,780 C240,760 420,640 700,650 C980,660 1100,470 1440,400"
                    fill="none"
                    stroke="#22d3ee"
                    strokeWidth="1.5"
                    strokeOpacity="0.35"
                />
            </svg>

            {/* Dim the art and darken the edges so the card reads clearly. */}
            <div className="absolute inset-0 bg-[#070b14]/55" />
            <div
                className="absolute inset-0"
                style={{
                    background:
                        "radial-gradient(ellipse 82% 72% at 50% 42%, transparent 28%, rgba(7,11,20,0.88) 100%)",
                }}
            />
        </div>
    );
}
