"use client";

import { useState } from "react";
import { Share2, Check, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";

export function ShareButton({ sessionId, currentMessages }: { sessionId: string, currentMessages: any[] }) {
    const [isSharing, setIsSharing] = useState(false);
    const [shareUrl, setShareUrl] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    // In a real application, you'd send an API request to generate a token and store the session data.
    const handleShare = async () => {
        setIsSharing(true);
        try {
            const res = await api.createShareLink(sessionId, currentMessages);
            const url = `${window.location.origin}/shared/${res.token}`;
            setShareUrl(url);
        } catch (e) {
            console.error("Share failed", e);
        } finally {
            setIsSharing(false);
        }
    };

    const copyToClipboard = async () => {
        if (shareUrl) {
            await navigator.clipboard.writeText(shareUrl);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    if (shareUrl) {
        return (
            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-2">
                    Share Link:
                </span>
                <input
                    type="text"
                    readOnly
                    value={shareUrl}
                    className="text-xs px-2 py-1.5 bg-gray-50 border border-gray-200 rounded w-64 text-gray-600 focus:outline-none"
                />
                <button
                    onClick={copyToClipboard}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-purple-50 text-purple-700 rounded-md hover:bg-purple-100 transition-colors"
                >
                    {copied ? <Check size={14} className="text-green-600" /> : <Share2 size={14} />}
                    {copied ? "Copied" : "Copy"}
                </button>
                <a
                    href={shareUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-gray-600 ml-1"
                >
                    <ExternalLink size={14} />
                </a>
            </div>
        );
    }

    return (
        <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-2">
                Collaborate:
            </span>
            <button
                onClick={handleShare}
                disabled={isSharing}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 rounded-md disabled:opacity-50 transition-colors"
            >
                <Share2 size={14} />
                {isSharing ? "Generating..." : "Generate Share Link"}
            </button>
        </div>
    );
}
