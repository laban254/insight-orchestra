"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";

// Public even when auth is on: a share link is meant to be opened by anyone
// who has the (unguessable) token, account or not — matches the backend's
// GET /sessions/shared/{token}, which stays unauthenticated by design.
const PUBLIC_PATHS = ["/login", "/shared"];

function AuthGate({ children }: { children: React.ReactNode }) {
    const { authEnabled, user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));

    useEffect(() => {
        if (!loading && authEnabled && !user && !isPublic) {
            router.replace("/login");
        }
    }, [loading, authEnabled, user, isPublic, router]);

    if (!loading && authEnabled && !user && !isPublic) {
        // Redirecting — render nothing rather than flashing the app underneath.
        return null;
    }
    return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <ThemeProvider>
            <ToastProvider>
                <AuthProvider>
                    <AuthGate>{children}</AuthGate>
                </AuthProvider>
            </ToastProvider>
        </ThemeProvider>
    );
}
