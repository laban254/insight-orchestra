"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";
interface Toast {
    id: number;
    kind: ToastKind;
    message: string;
}

const ToastCtx = createContext<(message: string, kind?: ToastKind) => void>(() => {});

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info };
const TINTS: Record<ToastKind, string> = {
    success: "text-success",
    error: "text-danger",
    info: "text-accent",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const remove = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

    const push = useCallback(
        (message: string, kind: ToastKind = "info") => {
            const id = Date.now() + Math.random();
            setToasts((t) => [...t, { id, kind, message }]);
            setTimeout(() => remove(id), 4200);
        },
        [remove]
    );

    return (
        <ToastCtx.Provider value={push}>
            {children}
            <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 max-w-[90vw] flex-col gap-2">
                {toasts.map((t) => {
                    const Icon = ICONS[t.kind];
                    return (
                        <div
                            key={t.id}
                            className="animate-rise pointer-events-auto flex items-start gap-2.5 rounded-xl border border-border bg-surface px-3.5 py-3 shadow-[var(--shadow)]"
                        >
                            <Icon size={16} className={`mt-0.5 shrink-0 ${TINTS[t.kind]}`} />
                            <p className="min-w-0 flex-1 text-sm text-fg">{t.message}</p>
                            <button onClick={() => remove(t.id)} className="text-faint transition-colors hover:text-fg">
                                <X size={14} />
                            </button>
                        </div>
                    );
                })}
            </div>
        </ToastCtx.Provider>
    );
}

export function useToast() {
    return useContext(ToastCtx);
}
