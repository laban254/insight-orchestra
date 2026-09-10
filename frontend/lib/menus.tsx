"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
    type Dispatch,
    type SetStateAction,
} from "react";

/**
 * One dropdown menu open at a time, app-wide.
 *
 * Each header menu (model switcher, export, user, dataset switch) used to
 * carry its own `useState` + `mousedown` listener — and one of them
 * (dataset switch) had none at all, so it stayed stuck open. This makes
 * opening any menu close the others, and `Escape` / a click outside close
 * the active one, from a single place.
 */

interface MenuCtx {
    openId: string | null;
    setOpenId: Dispatch<SetStateAction<string | null>>;
}

const Ctx = createContext<MenuCtx | null>(null);

export function MenuProvider({ children }: { children: React.ReactNode }) {
    const [openId, setOpenId] = useState<string | null>(null);

    useEffect(() => {
        if (!openId) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpenId(null);
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [openId]);

    return <Ctx.Provider value={{ openId, setOpenId }}>{children}</Ctx.Provider>;
}

/** Imperatively close whatever menu is open — for full-screen overlays
 *  (command palette, drawers) that should take over when they appear. */
export function useCloseMenus() {
    const ctx = useContext(Ctx);
    return useCallback(() => ctx?.setOpenId(null), [ctx]);
}

/**
 * Drive one dropdown. Spread `ref` on the menu's outermost element so an
 * outside click can close it.
 */
export function useMenu(id: string) {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error("useMenu must be used within MenuProvider");
    const { openId, setOpenId } = ctx;
    const open = openId === id;
    const ref = useRef<HTMLDivElement>(null);

    const close = useCallback(
        () => setOpenId((cur) => (cur === id ? null : cur)),
        [id, setOpenId]
    );
    const toggle = useCallback(
        () => setOpenId((cur) => (cur === id ? null : id)),
        [id, setOpenId]
    );

    useEffect(() => {
        if (!open) return;
        const onDown = (e: PointerEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) close();
        };
        // pointerdown fires before the click's focus shuffle — closes reliably
        document.addEventListener("pointerdown", onDown);
        return () => document.removeEventListener("pointerdown", onDown);
    }, [open, close]);

    return { open, toggle, close, ref };
}
