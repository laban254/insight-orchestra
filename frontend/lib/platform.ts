"use client";

import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

/**
 * The label for the primary modifier key — "⌘" on Apple platforms, "Ctrl"
 * everywhere else — so the shortcut hint matches the keyboard the user is
 * actually on. Both keys work at runtime (see CommandPalette); this is only
 * about what we tell them to press.
 *
 * Read through useSyncExternalStore so the server snapshot ("Ctrl") is used
 * for hydration and the real platform value swaps in without a mismatch.
 */
export function useModifierKeyLabel(): string {
    return useSyncExternalStore(
        emptySubscribe,
        () => (/Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? "⌘" : "Ctrl"),
        () => "Ctrl"
    );
}
