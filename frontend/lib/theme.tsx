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
        // Dark-first: the app's canonical look matches the auth + marketing
        // surfaces. Light is still available via the toggle, but dark is the
        // default whenever the user hasn't chosen one.
        const stored = localStorage.getItem("io-theme") as Theme | null;
        const initial = stored ?? "dark";
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setThemeState(initial);
        apply(initial);
        // Enable color transitions only after first paint to avoid a flash.
        requestAnimationFrame(() => document.documentElement.classList.add("theme-ready"));
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
