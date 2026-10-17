"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "./runtimeEnv";

export type BackendStatus = "checking" | "online" | "offline";

/**
 * Polls the unauthenticated `/health` endpoint until the backend answers, then
 * stops. This exists because a first run is slow by design: uvicorn binds the
 * port almost immediately, but each worker still imports pandas, statsmodels
 * and the agent SDK before it can serve a request (a measured cold start was
 * ~64s). Without this the UI just spins or fails silently for the first minute.
 */
export function useBackendHealth(pollMs = 4000) {
    const [status, setStatus] = useState<BackendStatus>("checking");
    const [nonce, setNonce] = useState(0);

    const check = useCallback(async () => {
        const ctrl = new AbortController();
        const timeout = setTimeout(() => ctrl.abort(), 3500);
        try {
            const res = await fetch(`${getApiBaseUrl()}/health`, {
                signal: ctrl.signal,
                cache: "no-store",
            });
            return res.ok;
        } catch {
            return false;
        } finally {
            clearTimeout(timeout);
        }
    }, []);

    useEffect(() => {
        let cancelled = false;
        let timer: ReturnType<typeof setTimeout>;
        const run = async () => {
            const ok = await check();
            if (cancelled) return;
            setStatus(ok ? "online" : "offline");
            // Keep polling while it's down so the banner clears itself the
            // moment the backend finishes booting.
            if (!ok) timer = setTimeout(run, pollMs);
        };
        void run();
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [check, pollMs, nonce]);

    const recheck = useCallback(() => {
        setStatus("checking");
        setNonce((n) => n + 1);
    }, []);

    return { status, recheck };
}
