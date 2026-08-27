/**
 * Where the *browser* should reach the backend.
 *
 * This deliberately isn't a `NEXT_PUBLIC_` build-time constant. Next inlines
 * those during `next build`, so the published Docker image would carry
 * whatever host it was built with — `http://localhost:8000`. That's correct
 * only when you browse from the same machine that runs Docker. Anyone
 * self-hosting on a homelab box, NAS, or VPS and opening the UI from a laptop
 * would have their browser resolve `localhost` to the laptop and fail every
 * request.
 *
 * Instead the server injects the value per request into `window.__IO_ENV__`
 * (see app/layout.tsx), so one image serves every deployment. The
 * `NEXT_PUBLIC_API_URL` fallback keeps `next dev` and existing local setups
 * working unchanged.
 */

declare global {
    interface Window {
        __IO_ENV__?: { apiBaseUrl?: string };
    }
}

export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

/** Resolved once per environment: injected value in the browser, env on the server. */
export function getApiBaseUrl(): string {
    if (typeof window !== 'undefined' && window.__IO_ENV__?.apiBaseUrl) {
        return window.__IO_ENV__.apiBaseUrl;
    }
    return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL;
}
