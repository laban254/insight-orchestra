/**
 * The auth brand backdrop: a deep navy field lit by cyan / violet / fuchsia
 * glows — the marketing site's `--gradient-bg`, adapted for the app. Pure CSS,
 * no animation, no image.
 */
export function AuthBackdrop() {
    return (
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden bg-[#0a0f1e]">
            <div className="absolute inset-0 bg-auth-glow" />
        </div>
    );
}
