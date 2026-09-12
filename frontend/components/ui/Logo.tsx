// The mark: a ring with one node breaking away — agents orbiting a shared
// finding. Bold enough to still read at favicon scale; see app/icon.svg
// and app/favicon.ico, which render the same shape standalone.
function Mark({ size }: { size: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="6.3" stroke="currentColor" strokeWidth="1.8" />
            <circle cx="15.6" cy="6.85" r="2.6" fill="currentColor" />
        </svg>
    );
}

export function Logo({ size = 8 }: { size?: number }) {
    return (
        <div
            className="grid place-items-center rounded-xl bg-accent text-accent-fg"
            style={{ width: `${size * 4}px`, height: `${size * 4}px` }}
        >
            <Mark size={size * 2.2} />
        </div>
    );
}
