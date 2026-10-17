"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useBackendHealth } from "@/lib/useBackendHealth";

/**
 * Tells the truth during the first-run cold start instead of leaving the user
 * on a spinner that looks broken. Hidden as soon as /health responds.
 */
export function BackendStatusBanner() {
    const { status, recheck } = useBackendHealth();
    if (status !== "offline") return null;

    return (
        <div
            role="status"
            className="fixed inset-x-0 top-0 z-[80] flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-warning/40 bg-warning/15 px-4 py-2 text-center text-xs text-warning backdrop-blur"
        >
            <Loader2 size={13} className="animate-spin" aria-hidden="true" />
            <span>
                The backend is still starting — a first run has to load pandas and statsmodels, which can
                take a minute.
            </span>
            <button
                onClick={recheck}
                className="inline-flex items-center gap-1 rounded-md border border-warning/40 px-2 py-0.5 font-medium transition-colors hover:bg-warning/20"
            >
                <RefreshCw size={11} aria-hidden="true" /> Check again
            </button>
        </div>
    );
}
