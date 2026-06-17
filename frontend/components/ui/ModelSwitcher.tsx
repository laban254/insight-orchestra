"use client";

import { useEffect, useRef, useState } from "react";
import { Cpu, ChevronDown, Check, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { AppConfig } from "@/lib/types";
import { useToast } from "@/lib/toast";

const LABELS: Record<string, string> = {
    ollama: "Ollama (local)",
    deepseek: "DeepSeek",
    openai: "OpenAI",
    anthropic: "Anthropic",
};

export function ModelSwitcher() {
    const [config, setConfig] = useState<AppConfig | null>(null);
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const toast = useToast();

    useEffect(() => {
        api.getConfig().then(setConfig).catch(() => {});
    }, []);

    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", onClick);
        return () => document.removeEventListener("mousedown", onClick);
    }, []);

    if (!config) return null;

    const choose = async (provider: string) => {
        if (provider === config.provider) return setOpen(false);
        setBusy(true);
        try {
            const next = await api.setConfig({ provider });
            setConfig({ ...config, ...next });
            toast(`Switched to ${LABELS[next.provider] ?? next.provider}`, "success");
            setOpen(false);
        } catch (e: unknown) {
            const detail =
                typeof e === "object" && e !== null && "response" in e
                    ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
                    : null;
            toast(detail ?? "Could not switch model", "error");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs font-medium text-muted transition-colors hover:text-fg"
                title="Switch model"
            >
                {busy ? <Loader2 size={14} className="animate-spin text-accent" /> : <Cpu size={14} className="text-accent" />}
                <span className="hidden font-mono sm:inline">{config.model}</span>
                <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open && (
                <div className="absolute right-0 z-30 mt-1.5 w-56 overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow)]">
                    <p className="border-b border-border-soft px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-faint">
                        LLM provider
                    </p>
                    {config.available.map((p) => {
                        const ready = config.ready[p];
                        const active = p === config.provider;
                        return (
                            <button
                                key={p}
                                disabled={!ready}
                                onClick={() => choose(p)}
                                className="flex w-full items-center justify-between px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                <span className={active ? "font-medium text-fg" : "text-muted"}>{LABELS[p] ?? p}</span>
                                {active ? (
                                    <Check size={14} className="text-accent" />
                                ) : !ready ? (
                                    <span className="text-[10px] text-faint">no key</span>
                                ) : null}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
