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
    /** Self-serve sign-up is allowed (auth on AND server ALLOW_SIGNUP=true). */
    signupEnabled: boolean;
    user: AuthUser | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (name: string, email: string, password: string) => Promise<void>;
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
    const [signupEnabled, setSignupEnabled] = useState(false);
    const [user, setUser] = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            const { data } = await authClient.get("/auth/me");
            setAuthEnabled(!!data.auth_enabled);
            setOidcConfigured(!!data.oidc_configured);
            setSignupEnabled(!!data.signup_enabled);
            setUser(data.user ?? null);
        } catch {
            // An unreachable /auth/me shouldn't strand the app on a loading
            // screen — fail open to "no auth", same as an unconfigured server.
            setAuthEnabled(false);
            setOidcConfigured(false);
            setSignupEnabled(false);
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

    const register = useCallback(async (name: string, email: string, password: string) => {
        const { data } = await authClient.post("/auth/register", { name, email, password });
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
                signupEnabled,
                user,
                loading,
                login,
                register,
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

// Higher rank = more capability. `admin` is the superset role (the backend's
// require_role treats it as satisfying every requirement), so a single
// comparison covers "at least this role".
const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2 };

/**
 * The caller's effective role for gating UI. With auth off, everyone is
 * effectively admin — the backend's auth dependencies are no-ops there, so the
 * UI must not hide controls the server would happily accept.
 */
export function useRole(): Role {
    const { authEnabled, user } = useAuth();
    if (!authEnabled) return "admin";
    return user?.role ?? "viewer";
}

/**
 * Whether the caller may perform an action requiring at least `min`.
 *
 * Mirrors the backend's require_role() so the UI hides or disables what the
 * server would 403, instead of letting someone submit a form that always
 * fails. Returns false while signed out (nobody to evaluate).
 */
export function useCan(min: Role): boolean {
    const { authEnabled, user } = useAuth();
    if (!authEnabled) return true;
    if (!user) return false;
    return RANK[user.role] >= RANK[min];
}

/** True once we know it's safe to show admin-only controls (auth off, or on and admin). */
export function useIsAdmin(): boolean {
    return useCan("admin");
}
