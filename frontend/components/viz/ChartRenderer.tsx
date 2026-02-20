"use client";

import dynamic from 'next/dynamic';

// Next.js dynamic import because Plotly doesn't run well on the server
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false, loading: () => <div className="animate-pulse bg-gray-100 rounded-lg h-[400px] w-full flex items-center justify-center text-gray-400">Loading Chart...</div> });

interface ChartRendererProps {
    plotJsonStr: string;
}

export function ChartRenderer({ plotJsonStr }: ChartRendererProps) {
    let data = [];
    let layout = {};

    try {
        const parsed = JSON.parse(plotJsonStr);
        data = parsed.data || [];
        layout = parsed.layout || {};

        // Autoresize and styling
        layout = {
            ...layout,
            autosize: true,
            margin: { l: 40, r: 20, t: 40, b: 40 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {
                family: 'Inter, system-ui, sans-serif'
            }
        };
    } catch (e) {
        console.error("Failed to parse plot JSON", e);
        return <div className="p-4 text-red-500 bg-red-50 rounded-lg text-sm border border-red-100">Chart data invalid or empty</div>;
    }

    return (
        <div className="w-full my-6 bg-white border border-gray-100 p-2 rounded-xl shadow-sm">
            <Plot
                data={data}
                layout={layout}
                useResizeHandler={true}
                style={{ width: "100%", height: "400px" }}
                config={{ responsive: true, displayModeBar: true, displaylogo: false }}
            />
        </div>
    );
}
