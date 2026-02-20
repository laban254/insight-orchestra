"use client";

import Editor from "@monaco-editor/react";
import { useState } from "react";
import { Copy, Play, Check } from "lucide-react";

interface CodeBlockProps {
    code: string;
    language?: string;
    onRunAgain?: () => void;
}

export function CodeBlock({ code, language = "python", onRunAgain }: CodeBlockProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="rounded-lg border border-gray-200 overflow-hidden my-4 shadow-sm">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 bg-gray-900">
                <span className="text-xs text-gray-400 font-mono">
                    Generated API Sandbox
                </span>
                <div className="flex gap-3">
                    <button
                        onClick={handleCopy}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors focus:outline-none"
                    >
                        {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                        {copied ? <span className="text-green-400">Copied</span> : "Copy"}
                    </button>
                    {onRunAgain && (
                        <button
                            onClick={onRunAgain}
                            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors focus:outline-none"
                        >
                            <Play size={14} />
                            Run again
                        </button>
                    )}
                </div>
            </div>

            {/* Monaco Editor (read-only display) */}
            <div className="bg-[#1e1e1e] p-2">
                <Editor
                    height="300px" // Dynamic or fixed
                    language={language}
                    value={code}
                    theme="vs-dark"
                    options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 13,
                        lineNumbers: "on",
                        wordWrap: "on",
                        automaticLayout: true,
                        renderLineHighlight: "none",
                        hideCursorInOverviewRuler: true
                    }}
                />
            </div>
        </div>
    );
}
