"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { Download } from "lucide-react";
import { useTheme } from "@/lib/theme";

const Plot = dynamic(() => import("react-plotly.js"), {
    ssr: false,
    loading: () => (
        <div className="relative h-[360px] w-full overflow-hidden rounded-xl border border-border bg-surface-2">
            <div className="shimmer absolute inset-0" />
        </div>
    ),
});

const COLORWAY = ["#22d3ee", "#e879f9", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#60a5fa", "#f97316"];

interface ChartRendererProps {
    plotJsonStr: string;
    height?: number;
}

interface Trace {
    type?: string;
    name?: string;
    x?: unknown;
    y?: unknown;
}

/** A one-line, screen-reader-friendly description of what the chart shows. */
function describeChart(data: Trace[]): string {
    const parts = data.map((t) => {
        const kind = t.type ?? "scatter";
        const n = Array.isArray(t.x) ? t.x.length : Array.isArray(t.y) ? t.y.length : 0;
        const name = t.name ? ` "${t.name}"` : "";
        return `${kind}${name}${n ? ` (${n} points)` : ""}`;
    });
    return parts.length ? `Chart: ${parts.join("; ")}.` : "Chart";
}

function csvCell(value: unknown): string {
    if (value == null) return "";
    const s = typeof value === "object" ? JSON.stringify(value) : String(value);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Serialize the chart's underlying data to CSV — one "index,x,y" block per trace. */
function tracesToCsv(data: Trace[]): string {
    const lines: string[] = [];
    data.forEach((t, i) => {
        const xs = Array.isArray(t.x) ? t.x : [];
        const ys = Array.isArray(t.y) ? t.y : [];
        lines.push(`# ${t.name ?? `series ${i + 1}`}`);
        lines.push("index,x,y");
        const len = Math.max(xs.length, ys.length);
        for (let r = 0; r < len; r++) {
            lines.push(`${r},${csvCell(xs[r])},${csvCell(ys[r])}`);
        }
        lines.push("");
    });
    return lines.join("\n");
}

export function ChartRenderer({ plotJsonStr, height = 360 }: ChartRendererProps) {
    const { theme } = useTheme();
    const isDark = theme === "dark";

    const parsed = useMemo(() => {
        try {
            const p = JSON.parse(plotJsonStr);
            const layout = { ...(p.layout ?? {}) };
            // Plotly Express bakes a full `template` into every figure — its own
            // colorway, an opaque paper background, light-mode fonts. It wins
            // over the theme overrides below, which is why in-app charts render
            // off-brand (purple bars, white panels). Drop it.
            delete layout.template;
            // The generated figure's title is almost always the bare column
            // name ("region"), which then also shows as the axis label. The
            // card/section above the chart already carries a real title.
            delete layout.title;
            return { data: Array.isArray(p.data) ? (p.data as Trace[]) : [], layout };
        } catch {
            return null;
        }
    }, [plotJsonStr]);

    const summary = useMemo(() => (parsed ? describeChart(parsed.data) : ""), [parsed]);

    if (!parsed) {
        return (
            <div role="alert" className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
                Chart data invalid or empty
            </div>
        );
    }
    if (!Array.isArray(parsed.data) || parsed.data.length === 0) return null;

    const fg = isDark ? "#9aa7c2" : "#4a566b";
    const grid = isDark ? "rgba(232,238,252,0.08)" : "rgba(11,18,32,0.08)";
    const axis = isDark ? "rgba(232,238,252,0.15)" : "rgba(11,18,32,0.15)";

    // A bar chart with a non-zero baseline distorts the visual comparison
    // (a bar half as tall can be 90% of the value). Force the value axis to
    // start at zero and ignore any range the generator picked.
    const hasBar = parsed.data.some((t) => t?.type === "bar");
    const forceZero = hasBar ? { rangemode: "tozero" as const, range: undefined, autorange: true } : {};

    const layout = {
        ...parsed.layout,
        autosize: true,
        margin: { l: 48, r: 20, t: 16, b: 44 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        colorway: COLORWAY,
        font: { family: "var(--font-inter), system-ui, sans-serif", color: fg, size: 12 },
        xaxis: { gridcolor: grid, linecolor: axis, zerolinecolor: axis, ...(parsed.layout?.xaxis ?? {}), ...forceZero },
        yaxis: { gridcolor: grid, linecolor: axis, zerolinecolor: axis, ...(parsed.layout?.yaxis ?? {}), ...forceZero },
        legend: { font: { color: fg }, ...(parsed.layout?.legend ?? {}) },
        hoverlabel: {
            bgcolor: isDark ? "#161f33" : "#ffffff",
            bordercolor: isDark ? "#25314c" : "#d8dfea",
            font: { color: isDark ? "#e8eefc" : "#0b1220" },
        },
    };

    const downloadCsv = () => {
        const blob = new Blob([tracesToCsv(parsed.data)], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "chart-data.csv";
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="w-full overflow-hidden rounded-xl border border-border bg-surface">
            {/* Plotly's own modebar is hover-only, so touch users never see it.
                Keep a persistent, keyboard-reachable way out of the chart. */}
            <div className="flex items-center justify-end border-b border-border-soft px-2 py-1">
                <button
                    onClick={downloadCsv}
                    className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-faint transition-colors hover:text-fg"
                    aria-label="Download chart data as CSV"
                >
                    <Download size={12} aria-hidden="true" /> CSV
                </button>
            </div>
            <div role="group" aria-label={summary} className="p-2">
                <Plot
                    data={parsed.data}
                    layout={layout}
                    useResizeHandler
                    style={{ width: "100%", height: `${height}px` }}
                    config={{ responsive: true, displaylogo: false, displayModeBar: "hover" }}
                />
            </div>
        </div>
    );
}
