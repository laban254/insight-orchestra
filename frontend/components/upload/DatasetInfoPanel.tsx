"use client";

import { X, ChevronDown, Table2 } from "lucide-react";
import { useState } from "react";
import { DemoDataset } from "@/lib/types";

interface DatasetInfo {
    name: string;
    type: "uploaded" | "demo";
    rows: number | string;
    columns: number | string;
    description?: string;
    use_cases?: string[];
}

export function DatasetInfoPanel({
    info,
    onReset,
    onSwitch,
    availableDatasets,
}: {
    info: DatasetInfo | null;
    onReset: () => void;
    onSwitch?: (datasetId: string) => void | Promise<void>;
    availableDatasets?: Record<string, DemoDataset> | null;
}) {
    const [showMenu, setShowMenu] = useState(false);

    if (!info) return null;

    return (
        <div className="flex items-center gap-1.5">
            {/* Dataset badge */}
            <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5">
                <Table2 size={14} className="text-accent" />
                <div className="leading-tight">
                    <p className="max-w-[160px] truncate text-xs font-medium text-fg">{info.name}</p>
                    <p className="font-mono text-[10px] text-faint">
                        {info.rows} rows · {info.columns} cols
                    </p>
                </div>
            </div>

            {/* Switch */}
            {onSwitch && availableDatasets && (
                <div className="relative">
                    <button
                        onClick={() => setShowMenu((v) => !v)}
                        className="flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs font-medium text-muted transition-colors hover:text-fg"
                        title="Switch dataset"
                    >
                        Switch
                        <ChevronDown size={13} className={`transition-transform ${showMenu ? "rotate-180" : ""}`} />
                    </button>

                    {showMenu && (
                        <div className="absolute right-0 z-30 mt-1.5 w-52 overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow)]">
                            {Object.entries(availableDatasets).map(([id, config]) => (
                                <button
                                    key={id}
                                    onClick={() => {
                                        onSwitch?.(id);
                                        setShowMenu(false);
                                    }}
                                    className="w-full border-b border-border-soft px-3 py-2 text-left transition-colors last:border-0 hover:bg-surface-2"
                                >
                                    <p className="text-xs font-medium text-fg">{config.name}</p>
                                    <p className="font-mono text-[10px] text-faint">{config.rows} rows</p>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <button
                onClick={onReset}
                className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:border-danger/40 hover:text-danger"
                title="Use a different dataset"
            >
                <X size={15} />
            </button>
        </div>
    );
}
