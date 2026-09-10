"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, Shield, User } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Signed-in user badge + logout. Renders nothing when auth is off or no one is signed in. */
export function UserMenu() {
    const { authEnabled, user, logout } = useAuth();
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", onClick);
        return () => document.removeEventListener("mousedown", onClick);
    }, []);

    if (!authEnabled || !user) return null;

    const handleLogout = async () => {
        await logout();
        router.replace("/login");
    };

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs font-medium text-muted transition-colors hover:text-fg"
                title={user.email}
            >
                <User size={14} className="text-accent" />
                <span className="hidden max-w-[8rem] truncate sm:inline">{user.name || user.email}</span>
                <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open && (
                <div className="absolute right-0 z-30 mt-1.5 w-52 overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow)]">
                    <div className="border-b border-border-soft px-3 py-2.5">
                        <p className="truncate text-sm font-medium text-fg">{user.email}</p>
                        <p className="mt-0.5 text-[10px] uppercase tracking-wider text-faint">{user.role}</p>
                    </div>
                    {user.role === "admin" && (
                        <Link
                            href="/admin"
                            onClick={() => setOpen(false)}
                            className="flex w-full items-center gap-2 border-b border-border-soft px-3 py-2.5 text-left text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg"
                        >
                            <Shield size={14} /> Admin panel
                        </Link>
                    )}
                    <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg"
                    >
                        <LogOut size={14} /> Sign out
                    </button>
                </div>
            )}
        </div>
    );
}
