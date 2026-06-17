"use client";

import { Coins } from "lucide-react";

export function CostMeter({ tokens, cost }: { tokens: number; cost: number }) {
    if (tokens <= 0) return null;
    const tokenLabel = tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : String(tokens);
    return (
        <div
            className="hidden items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs text-muted md:flex"
            title={`${tokens.toLocaleString()} tokens · $${cost.toFixed(4)} this session`}
        >
            <Coins size={13} className="text-warning" />
            <span className="font-mono">{tokenLabel}</span>
            <span className="text-faint">·</span>
            <span className="font-mono">${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}</span>
        </div>
    );
}
