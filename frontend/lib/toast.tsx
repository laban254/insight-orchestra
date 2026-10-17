"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";

export interface ToastAction {
    label: string;
    onClick: () => void;
}

interface Toast {
    id: number;
    kind: ToastKind;
    message: string;
    action?: ToastAction;
}

type PushToast = (message: string, kind?: ToastKind, action?: ToastAction) => void;

const ToastCtx = createContext<PushToast>(() => {});

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info };
const TINTS: Record<ToastKind, string> = {
    success: "text-success",
    error: "text-danger",
    info: "text-accent",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

    const remove = useCallback((id: number) => {
        const t = timers.current.get(id);
        if (t) {
            clearTimeout(t);
            timers.current.delete(id);
        }
        setToasts((list) => list.filter((x) => x.id !== id));
    }, []);

    const push = useCallback<PushToast>(
        (message, kind = "info", action) => {
            const id = Date.now() + Math.random();
            setToasts((list) => [...list, { id, kind, message, action }]);
            // An actionable toast (Undo, Retry) needs a longer window than a
            // passive confirmation, or it's gone before it can be clicked.
            const ttl = action ? 8000 : kind === "error" ? 6000 : 4200;
            timers.current.set(
                id,
                setTimeout(() => remove(id), ttl)
            );
        },
        [remove]
    );

    useEffect(
        () => () => {
            timers.current.forEach(clearTimeout);
            timers.current.clear();
        },
        []
    );

    return (
        <ToastCtx.Provider value={push}>
            {children}
            {/* Top-center on phones (the composer sits at the bottom there),
                bottom-right on larger screens. Each toast carries its own live
                role so screen readers announce it without us announcing the
                whole region as one blob. */}
            <div
                aria-label="Notifications"
                className="pointer-events-none fixed inset-x-0 top-4 z-[90] mx-auto flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:top-auto sm:mx-0"
            >
                {toasts.map((t) => {
                    const Icon = ICONS[t.kind];
                    return (
                        <div
                            key={t.id}
                            role={t.kind === "error" ? "alert" : "status"}
                            className="animate-rise pointer-events-auto flex items-start gap-2.5 rounded-xl border border-border bg-surface px-3.5 py-3 shadow-[var(--shadow)]"
                        >
                            <Icon size={16} aria-hidden="true" className={`mt-0.5 shrink-0 ${TINTS[t.kind]}`} />
                            <p className="min-w-0 flex-1 text-sm text-fg">{t.message}</p>
                            {t.action && (
                                <button
                                    onClick={() => {
                                        t.action?.onClick();
                                        remove(t.id);
                                    }}
                                    className="shrink-0 rounded-md px-1.5 py-0.5 text-xs font-semibold text-accent transition-colors hover:bg-accent-soft/40"
                                >
                                    {t.action.label}
                                </button>
                            )}
                            <button
                                onClick={() => remove(t.id)}
                                aria-label="Dismiss notification"
                                className="text-faint transition-colors hover:text-fg"
                            >
                                <X size={14} aria-hidden="true" />
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
