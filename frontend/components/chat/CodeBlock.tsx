"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronUp, Copy } from "lucide-react";

interface CodeBlockProps {
    code: string;
    language?: string;
}

const COLLAPSE_THRESHOLD = 12; // lines before the "show all" toggle appears

const KEYWORDS = new Set([
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
    "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with",
    "yield", "True", "False", "None",
]);
const BUILTINS = new Set([
    "print", "len", "range", "list", "dict", "set", "tuple", "int", "float", "str", "bool",
    "sum", "min", "max", "sorted", "abs", "round", "zip", "map", "filter", "enumerate",
    "df", "pd", "np", "px", "go", "result", "fig",
]);

type Tok = { t: string; c?: string };

// Tiny single-pass Python tokenizer — enough for the short generated
// snippets we show. Not a real parser; unknown text falls through as plain.
function tokenize(src: string): Tok[] {
    const out: Tok[] = [];
    let i = 0;
    const push = (t: string, c?: string) => out.push({ t, c });
    while (i < src.length) {
        const ch = src[i];
        if (ch === "#") {
            let j = i;
            while (j < src.length && src[j] !== "\n") j++;
            push(src.slice(i, j), "comment");
            i = j;
        } else if (ch === '"' || ch === "'") {
            const q = ch;
            let j = i + 1;
            while (j < src.length && src[j] !== q) {
                if (src[j] === "\\") j++;
                j++;
            }
            j = Math.min(j + 1, src.length);
            push(src.slice(i, j), "string");
            i = j;
        } else if (/[0-9]/.test(ch)) {
            let j = i;
            while (j < src.length && /[0-9._eE]/.test(src[j])) j++;
            push(src.slice(i, j), "number");
            i = j;
        } else if (/[A-Za-z_]/.test(ch)) {
            let j = i;
            while (j < src.length && /[A-Za-z0-9_]/.test(src[j])) j++;
            const word = src.slice(i, j);
            push(word, KEYWORDS.has(word) ? "keyword" : BUILTINS.has(word) ? "builtin" : undefined);
            i = j;
        } else {
            let j = i;
            while (j < src.length && !/[#"'0-9A-Za-z_]/.test(src[j])) j++;
            push(src.slice(i, j));
            i = j;
        }
    }
    return out;
}

const TONE: Record<string, string> = {
    comment: "#6b7a99",
    string: "#7ee7c7",
    number: "#f0b866",
    keyword: "#c792ea",
    builtin: "#82aaff",
};

export function CodeBlock({ code }: CodeBlockProps) {
    const [copied, setCopied] = useState(false);
    const [expanded, setExpanded] = useState(false);

    const src = code || "";
    const lines = src.split("\n");
    const isLong = lines.length > COLLAPSE_THRESHOLD;
    const shown = isLong && !expanded ? lines.slice(0, COLLAPSE_THRESHOLD).join("\n") : src;
    const toks = useMemo(() => tokenize(shown), [shown]);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(src);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            /* clipboard blocked — no-op */
        }
    };

    return (
        <div className="w-full overflow-hidden rounded-xl border border-[#25314c] bg-[#0d1424]">
            <div className="flex items-center justify-between border-b border-[#1c2740] px-3.5 py-2">
                <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[#f0b866]" />
                    <span className="font-mono text-[11px] tracking-wide text-[#6b7a99]">Python · generated</span>
                </div>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1 text-[11px] text-[#6b7a99] transition-colors hover:text-[#c7d2e8]"
                >
                    {copied ? <Check size={12} className="text-[#7ee7c7]" /> : <Copy size={12} />}
                    {copied ? "Copied" : "Copy"}
                </button>
            </div>

            <pre className="overflow-x-auto px-4 py-3 font-mono text-[12.5px] leading-relaxed text-[#c7d2e8]">
                <code>
                    {toks.map((tk, n) =>
                        tk.c ? (
                            <span key={n} style={{ color: TONE[tk.c] }}>
                                {tk.t}
                            </span>
                        ) : (
                            <span key={n}>{tk.t}</span>
                        )
                    )}
                </code>
            </pre>

            {isLong && (
                <button
                    onClick={() => setExpanded((v) => !v)}
                    className="flex w-full items-center justify-center gap-1 border-t border-[#1c2740] py-1.5 text-[11px] text-[#6b7a99] transition-colors hover:bg-[#111a2e] hover:text-[#c7d2e8]"
                >
                    {expanded ? (
                        <>
                            <ChevronUp size={12} /> Collapse
                        </>
                    ) : (
                        <>
                            <ChevronDown size={12} /> Show all {lines.length} lines
                        </>
                    )}
                </button>
            )}
        </div>
    );
}
