"use client";

import { ChevronDown } from "lucide-react";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    /** Tighter padding + smaller text, for table cells and toolbars. */
    dense?: boolean;
    wrapperClassName?: string;
}

/**
 * A native <select> styled to match the app's inputs — the closed control
 * gets the theme's border/surface/text and a custom chevron; the option
 * list stays OS-native (keeps keyboard + a11y for free).
 */
export function Select({ className = "", wrapperClassName = "", dense = false, ...props }: SelectProps) {
    const field = dense ? "py-1 pl-2.5 pr-7 text-xs" : "py-2 pl-3 pr-9 text-sm";
    return (
        <div className={`relative ${wrapperClassName}`}>
            <select
                {...props}
                className={`w-full appearance-none rounded-lg border border-border bg-surface text-fg outline-none transition-colors focus:border-accent/60 disabled:opacity-50 ${field} ${className}`}
            />
            <ChevronDown
                size={dense ? 12 : 14}
                className={`pointer-events-none absolute top-1/2 -translate-y-1/2 text-faint ${dense ? "right-2" : "right-3"}`}
            />
        </div>
    );
}
