"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeCtx {
    theme: Theme;
    toggle: () => void;
    setTheme: (t: Theme) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

function apply(theme: Theme) {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    // Initial value mirrors the pre-paint script in layout.tsx.
    const [theme, setThemeState] = useState<Theme>("dark");

    useEffect(() => {
        const stored = (localStorage.getItem("io-theme") as Theme | null) ?? null;
        const system = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        const initial = stored ?? system;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setThemeState(initial);
        apply(initial);
        // Enable color transitions only after first paint to avoid a flash.
        requestAnimationFrame(() => document.documentElement.classList.add("theme-ready"));

        // Follow system changes only when the user hasn't pinned a choice.
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const onChange = (e: MediaQueryListEvent) => {
            if (!localStorage.getItem("io-theme")) {
                const next = e.matches ? "dark" : "light";
                setThemeState(next);
                apply(next);
            }
        };
        mq.addEventListener("change", onChange);
        return () => mq.removeEventListener("change", onChange);
    }, []);

    const setTheme = useCallback((t: Theme) => {
        localStorage.setItem("io-theme", t);
        setThemeState(t);
        apply(t);
    }, []);

    const toggle = useCallback(() => {
        setTheme(theme === "dark" ? "light" : "dark");
    }, [theme, setTheme]);

    return <Ctx.Provider value={{ theme, toggle, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme() {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
    return ctx;
}
