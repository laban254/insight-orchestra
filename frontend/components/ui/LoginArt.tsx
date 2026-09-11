// Hand-drawn hero for the login page's branding panel: scattered raw data
// converging through the 4-agent pipeline into a chart — the product's
// pitch as a picture, not a stock photo. No image asset, so it never goes
// stale, ships at zero bytes over the wire, and re-themes for free.
const RAW_POINTS: [number, number][] = [
    [40, 52],
    [66, 92],
    [30, 122],
    [80, 34],
    [54, 144],
];

const NODE_1 = [120, 90] as const;
const NODE_2 = [215, 45] as const;
const NODE_3 = [305, 107] as const;
const NODE_4 = [388, 62] as const;

const FLOW_PATH = `M${NODE_1[0]},${NODE_1[1]} C152,60 185,32 ${NODE_2[0]},${NODE_2[1]} C247,58 275,97 ${NODE_3[0]},${NODE_3[1]} C333,116 358,86 ${NODE_4[0]},${NODE_4[1]}`;

export function LoginArt() {
    return (
        <svg
            viewBox="0 0 480 220"
            className="h-full w-full overflow-visible"
            fill="none"
            aria-hidden
        >
            <defs>
                <linearGradient id="login-art-flow" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--border)" />
                    <stop offset="30%" stopColor="var(--accent)" />
                    <stop offset="65%" stopColor="var(--accent-2)" />
                    <stop offset="100%" stopColor="var(--accent)" />
                </linearGradient>
            </defs>

            {/* Raw, scattered data converging into the pipeline */}
            {RAW_POINTS.map(([x, y], i) => (
                <line
                    key={`t-${i}`}
                    x1={x}
                    y1={y}
                    x2={NODE_1[0]}
                    y2={NODE_1[1]}
                    stroke="var(--border)"
                    strokeWidth="1"
                    opacity="0.7"
                />
            ))}
            {RAW_POINTS.map(([x, y], i) => (
                <circle key={`p-${i}`} cx={x} cy={y} r="3" style={{ fill: "var(--faint)" }} />
            ))}

            {/* The pipeline itself, plus a soft traveling light to read as "live" */}
            <path d={FLOW_PATH} stroke="url(#login-art-flow)" strokeWidth="2" strokeLinecap="round" opacity="0.85" />
            <path
                d={FLOW_PATH}
                stroke="var(--accent)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray="8 40"
                className="animate-login-flow"
            />

            {/* Stage 1 — Data Janitor: cleaned, not yet analyzed */}
            <circle
                cx={NODE_1[0]}
                cy={NODE_1[1]}
                r="5"
                style={{ fill: "var(--surface)", stroke: "var(--border)", strokeWidth: 1.5 }}
            />
            {/* Stage 2 — Hypothesis Bot */}
            <circle cx={NODE_2[0]} cy={NODE_2[1]} r="6" style={{ fill: "var(--accent)" }} />
            {/* Stage 3 — Debate Manager */}
            <circle cx={NODE_3[0]} cy={NODE_3[1]} r="6" style={{ fill: "var(--accent-2)" }} />
            {/* Stage 4 — Viz Whiz: the consensus finding, breathing like a live result */}
            <circle
                cx={NODE_4[0]}
                cy={NODE_4[1]}
                r="14"
                style={{ fill: "var(--accent)", transformBox: "fill-box", transformOrigin: "center" }}
                className="animate-pulse-ring"
            />
            <circle cx={NODE_4[0]} cy={NODE_4[1]} r="7" style={{ fill: "var(--accent)" }} />

            {/* The payoff: an answer, rendered as a small rising chart */}
            <g style={{ fill: "var(--accent)" }}>
                <rect x="412" y="142" width="10" height="28" rx="2" opacity="0.45" />
                <rect x="430" y="112" width="10" height="58" rx="2" opacity="0.7" />
                <rect x="448" y="86" width="10" height="84" rx="2" />
            </g>
            <path
                d="M452 70 L456 74 L452 78 L448 74 Z"
                style={{ fill: "var(--accent-2)" }}
                className="animate-fade"
            />
        </svg>
    );
}
