"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

interface LazyMountProps {
    children: ReactNode;
    /** Reserved height for the placeholder, so mounting doesn't shift layout. */
    height: number;
    /** How far ahead of the viewport to start mounting. */
    rootMargin?: string;
}

/**
 * Defers mounting `children` until the wrapper scrolls near the viewport,
 * then mounts it permanently (a chart scrolling back off-screen keeps its
 * state rather than re-rendering on every re-entry). For a long results
 * list, each unmounted chart is one fewer live Plotly instance computing
 * layout and painting off-screen.
 */
export function LazyMount({ children, height, rootMargin = "200px" }: LazyMountProps) {
    const ref = useRef<HTMLDivElement>(null);
    // Environments without IntersectionObserver render immediately rather
    // than waiting on an effect that could never fire.
    const [visible, setVisible] = useState(() => typeof IntersectionObserver === "undefined");

    useEffect(() => {
        if (visible) return;
        const el = ref.current;
        if (!el) return;

        const observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    setVisible(true);
                    observer.disconnect();
                }
            },
            { rootMargin }
        );
        observer.observe(el);
        return () => observer.disconnect();
    }, [visible, rootMargin]);

    if (visible) return <>{children}</>;

    return (
        <div ref={ref} className="relative w-full overflow-hidden rounded-xl border border-border bg-surface-2" style={{ height }}>
            <div className="shimmer absolute inset-0" />
        </div>
    );
}
