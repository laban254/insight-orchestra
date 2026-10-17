// The mark: an "IO" monogram — a bar ("I") beside a ring ("O") for Insight
// Orchestra. Geometric (no font), so it stays crisp at favicon size. See
// app/icon.svg, app/apple-icon.png and app/favicon.ico, which render the same
// shape standalone.
export function LogoMark({ size = 24, className }: { size?: number; className?: string }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            className={className}
            aria-hidden
        >
            <rect x="2.9" y="4.5" width="3.2" height="15" rx="1.6" fill="currentColor" />
            <circle cx="14.3" cy="12" r="5.2" stroke="currentColor" strokeWidth="3.2" />
        </svg>
    );
}

export function Logo({ size = 8 }: { size?: number }) {
    return (
        <div
            className="grid place-items-center rounded-xl"
            style={{
                width: `${size * 4}px`,
                height: `${size * 4}px`,
                background: "linear-gradient(135deg,#00dffd,#b085ff 55%,#ff54f9)",
                boxShadow: "0 0 30px -12px rgb(0 223 253 / 0.7)",
            }}
        >
            <LogoMark size={size * 2.2} className="text-[#030b1c]" />
        </div>
    );
}
