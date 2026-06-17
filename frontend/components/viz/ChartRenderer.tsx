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
            return { data: p.data ?? [], layout: p.layout ?? {} };
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

    const layout = {
        ...parsed.layout,
        autosize: true,
        margin: { l: 48, r: 20, t: 36, b: 44 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        colorway: COLORWAY,
        font: { family: "var(--font-inter), system-ui, sans-serif", color: fg, size: 12 },
        title: parsed.layout?.title
            ? typeof parsed.layout.title === "string"
                ? { text: parsed.layout.title, font: { size: 14, color: fg } }
                : { ...parsed.layout.title, font: { size: 14, color: fg } }
            : undefined,
        xaxis: { gridcolor: grid, linecolor: axis, zerolinecolor: axis, ...(parsed.layout?.xaxis ?? {}) },
        yaxis: { gridcolor: grid, linecolor: axis, zerolinecolor: axis, ...(parsed.layout?.yaxis ?? {}) },
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
