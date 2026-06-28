"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Loader2, LinkIcon } from "lucide-react";
import { api } from "@/lib/api";
import { SharedReport, SharedPayload } from "@/components/share/SharedReport";

export default function SharedPage() {
    const params = useParams<{ token: string }>();
    const token = params?.token;
    const [data, setData] = useState<SharedPayload | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!token) return;
        api.getSharedSession(token)
            .then((d) => setData(d as SharedPayload))
            .catch(() => setError("This shared link is invalid or has expired."));
    }, [token]);

    if (error) {
        return (
            <main className="grid min-h-screen place-items-center bg-bg p-6">
                <div className="max-w-sm text-center">
                    <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-surface-2 text-faint">
                        <LinkIcon size={22} />
                    </div>
                    <h1 className="text-lg font-semibold text-fg">Link unavailable</h1>
                    <p className="mt-1.5 text-sm text-muted">{error}</p>
                    <Link
                        href="/"
                        className="mt-5 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90"
                    >
                        Go to Insight Orchestra
                    </Link>
                </div>
            </main>
        );
    }

    if (!data) {
        return (
            <main className="grid min-h-screen place-items-center bg-bg">
                <Loader2 className="animate-spin text-accent" size={28} />
            </main>
        );
    }

    return <SharedReport {...data} />;
}
