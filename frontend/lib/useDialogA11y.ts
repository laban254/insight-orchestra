"use client";

import { useEffect, useRef } from "react";

// Everything that can receive keyboard focus inside a dialog. Excludes
// disabled controls and negative tabindex, matching the browser's own order.
const FOCUSABLE =
    'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Dialog semantics for the app's overlays (command palette, history drawer):
 * moves focus into the dialog on open, traps Tab within it, and restores focus
 * to the element that opened it on close. Escape/backdrop handling stays with
 * each caller, which already owns its own close behavior.
 *
 * Spread the returned ref on the dialog's outer element and pair it with
 * `role="dialog" aria-modal="true"`.
 */
export function useDialogA11y<T extends HTMLElement = HTMLElement>(open: boolean) {
    const ref = useRef<T>(null);
    const restoreRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
        if (!open) return;
        restoreRef.current = document.activeElement as HTMLElement | null;
        const node = ref.current;

        const focusables = () =>
            Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
                (el) => el.offsetParent !== null || el === document.activeElement
            );

        // Prefer an explicit autofocus target (the palette's search input);
        // otherwise the first control, otherwise the container itself.
        const target = node?.querySelector<HTMLElement>("[data-autofocus]") ?? focusables()[0] ?? node;
        target?.focus?.();

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key !== "Tab") return;
            const items = focusables();
            if (items.length === 0) {
                e.preventDefault();
                return;
            }
            const first = items[0];
            const last = items[items.length - 1];
            const active = document.activeElement as HTMLElement | null;
            if (!e.shiftKey && active === last) {
                e.preventDefault();
                first.focus();
            } else if (e.shiftKey && active === first) {
                e.preventDefault();
                last.focus();
            }
        };

        document.addEventListener("keydown", onKeyDown, true);
        return () => {
            document.removeEventListener("keydown", onKeyDown, true);
            restoreRef.current?.focus?.();
        };
    }, [open]);

    return ref;
}
