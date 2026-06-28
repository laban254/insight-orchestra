"use client";

import { useEffect, useRef, useState } from "react";
import { Download, FileCode2, FileText, Table2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/lib/api";

function downloadUrl(url: string) {
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
}

export function ExportMenu({ sessionId, onReport }: { sessionId: string; onReport: () => void }) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const h = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, []);

    const item = (Icon: LucideIcon, label: string, sub: string, onClick: () => void) => (
        <button
            onClick={() => {
                onClick();
                setOpen(false);
            }}
            className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
        >
            <Icon size={15} className="mt-0.5 shrink-0 text-accent" />
            <span>
                <span className="block text-sm text-fg">{label}</span>
                <span className="block text-[11px] text-faint">{sub}</span>
            </span>
        </button>
    );

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen((o) => !o)}
                title="Export"
                className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-fg"
            >
                <Download size={16} />
            </button>
            {open && (
                <div className="absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow)]">
                    <p className="border-b border-border-soft px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-faint">
                        Export
                    </p>
                    {item(FileCode2, "Interactive report", "HTML with live charts", onReport)}
                    {item(FileText, "Summary", "Markdown report", () =>
                        downloadUrl(api.getExportUrl(sessionId, "markdown"))
                    )}
                    {item(Table2, "Q&A history", "CSV of your questions", () =>
                        downloadUrl(api.getExportUrl(sessionId, "csv"))
                    )}
                </div>
            )}
        </div>
    );
}
