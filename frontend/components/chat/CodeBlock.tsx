"use client";

import Editor from "@monaco-editor/react";
import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";

interface CodeBlockProps {
    code: string;
    language?: string;
}

const LINE_HEIGHT = 21;   // px per line in Monaco at fontSize 13
const MIN_HEIGHT  = 52;   // at least 2 visible lines
const MAX_HEIGHT  = 260;  // cap before we show "Expand"
const COLLAPSE_THRESHOLD = 10; // lines before the expand toggle appears

export function CodeBlock({ code, language = "python" }: CodeBlockProps) {
    const [copied,   setCopied]   = useState(false);
    const [expanded, setExpanded] = useState(false);

    const lines      = (code || "").split("\n").length;
    const isLong     = lines > COLLAPSE_THRESHOLD;
    const editorH    = Math.max(MIN_HEIGHT, Math.min(lines * LINE_HEIGHT, MAX_HEIGHT));
    const displayH   = isLong && !expanded ? Math.min(editorH, COLLAPSE_THRESHOLD * LINE_HEIGHT) : editorH;

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="rounded-xl border border-gray-200 overflow-hidden my-3 shadow-sm w-full">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 bg-gray-900">
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-yellow-400" />
                    <span className="text-xs text-gray-400 font-mono tracking-wide">
                        Python · Generated
                    </span>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={handleCopy}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors focus:outline-none"
                    >
                        {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                        <span className={copied ? "text-green-400" : ""}>{copied ? "Copied" : "Copy"}</span>
                    </button>
                </div>
            </div>

            {/* Monaco Editor — auto-sized */}
            <div className="bg-[#1e1e1e]" style={{ height: `${displayH}px`, overflow: "hidden" }}>
                <Editor
                    height={`${displayH}px`}
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
                        hideCursorInOverviewRuler: true,
                        scrollbar: { vertical: "hidden", horizontal: "hidden" },
                        overviewRulerLanes: 0,
                    }}
                />
            </div>

            {/* Expand / Collapse toggle for long blocks */}
            {isLong && (
                <button
                    onClick={() => setExpanded(v => !v)}
                    className="w-full flex items-center justify-center gap-1 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 text-xs transition-colors"
                >
                    {expanded
                        ? <><ChevronUp size={12} /> Collapse</>
                        : <><ChevronDown size={12} /> Show all {lines} lines</>
                    }
                </button>
            )}
        </div>
    );
}
