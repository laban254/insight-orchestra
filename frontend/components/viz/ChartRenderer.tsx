"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
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
            return { data: Array.isArray(p.data) ? p.data : [], layout };
        } catch {
            return null;
        }
    }, [plotJsonStr]);

    if (!parsed) {
        return (
            <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
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
    const hasBar = parsed.data.some((t: { type?: string }) => t?.type === "bar");
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

    return (
        <div className="w-full rounded-xl border border-border bg-surface p-2">
            <Plot
                data={parsed.data}
                layout={layout}
                useResizeHandler
                style={{ width: "100%", height: `${height}px` }}
                config={{ responsive: true, displaylogo: false, displayModeBar: "hover" }}
            />
        </div>
    );
}
