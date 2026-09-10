"use client";

import axios from "axios";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getApiBaseUrl } from "./runtimeEnv";

export type Role = "admin" | "member" | "viewer";

export interface AuthUser {
    id: string;
    email: string;
    name: string;
    role: Role;
    auth_provider: string;
    created_at: number;
    is_active: boolean;
}

interface AuthCtx {
    // Whether the server has AUTH_ENABLED=true at all — most of the app
    // (existing no-auth deployments) never sets this, so every consumer
    // must check it before treating `user` as meaningful.
    authEnabled: boolean;
    oidcConfigured: boolean;
    user: AuthUser | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    oidcLoginUrl: string;
    refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

const API_V1_URL = `${getApiBaseUrl()}/api/v1`;
// Separate from lib/api.ts's client: auth needs cookies sent (withCredentials),
// which the main client doesn't set since most deployments never enable auth.
const authClient = axios.create({ baseURL: API_V1_URL, withCredentials: true });

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [authEnabled, setAuthEnabled] = useState(false);
    const [oidcConfigured, setOidcConfigured] = useState(false);
    const [user, setUser] = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            const { data } = await authClient.get("/auth/me");
            setAuthEnabled(!!data.auth_enabled);
            setOidcConfigured(!!data.oidc_configured);
            setUser(data.user ?? null);
        } catch {
            // An unreachable /auth/me shouldn't strand the app on a loading
            // screen — fail open to "no auth", same as an unconfigured server.
            setAuthEnabled(false);
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const login = useCallback(async (email: string, password: string) => {
        const { data } = await authClient.post("/auth/login", { email, password });
        setUser(data.user);
    }, []);

    const logout = useCallback(async () => {
        await authClient.post("/auth/logout");
        setUser(null);
    }, []);

    return (
        <Ctx.Provider
            value={{
                authEnabled,
                oidcConfigured,
                user,
                loading,
                login,
                logout,
                oidcLoginUrl: `${API_V1_URL}/auth/oidc/login`,
                refresh,
            }}
        >
            {children}
        </Ctx.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}

/** True once we know it's safe to show admin-only controls (auth off, or on and admin). */
export function useIsAdmin(): boolean {
    const { authEnabled, user } = useAuth();
    return !authEnabled || user?.role === "admin";
}
