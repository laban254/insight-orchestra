"use client";

import { MessageCircle, Bot, Lightbulb } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { ChartRenderer } from "../viz/ChartRenderer";
import { useState } from "react";

export interface MessageProps {
    role: "user" | "assistant";
    content: string;
    code?: string | null;
    plotJson?: string | null;
    reasoning?: string | null;
    isError?: boolean;
}

export function MessageBubble({ role, content, code, plotJson, reasoning, isError }: MessageProps) {
    const isUser = role === "user";
    const [showReasoning, setShowReasoning] = useState(false);

    const getErrorContent = (errorMsg: string) => {
        if (!isError) return errorMsg;
        if (errorMsg.includes("401") || errorMsg.includes("invalid_api_key")) {
            return "🔑 Invalid API Key. Please check your `.env` configuration in the backend.";
        }
        if (errorMsg.includes("429")) {
            return "⏳ Rate limit reached. Please wait a moment or check your usage limits.";
        }
        return errorMsg;
    };

    // Format numbers dynamically (e.g. "The answer is 1000" -> bold the numbers)
    const formatContent = (text: string) => {
        if (isUser) return text;
        const msg = getErrorContent(text);

        // Simple bolding of numbers that appear at the end of "is X"
        return msg.split("\n").map((line, i) => {
            const bolded = line.replace(/\b(\d+(?:\.\d+)?)\b/g, (match) => `**${match}**`);
            // Custom rudimentary markdown-lite rendering to make answers pop
            const parts = bolded.split(/(\*\*.*?\*\*)/g);

            return (
                <span key={i} className="block mb-1 last:mb-0">
                    {parts.map((p, j) => {
                        if (p.startsWith("**") && p.endsWith("**")) {
                            return <strong key={j} className="font-bold text-gray-900">{p.slice(2, -2)}</strong>;
                        }
                        return <span key={j}>{p}</span>;
                    })}
                </span>
            );
        });
    };

    return (
        <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} my-4`}>
            <div className={`flex w-full max-w-[85%] gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}>

                {/* Avatar */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-sm
          ${isUser ? "bg-blue-600 text-white" : isError ? "bg-red-500 text-white" : "bg-purple-600 text-white"}`}
                >
                    {isUser ? <MessageCircle size={15} /> : <Bot size={15} />}
                </div>

                {/* Message Body */}
                <div className="flex flex-col gap-3 min-w-0 flex-1">

                    {/* Text content */}
                    {content && (
                        <div className={`px-5 py-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
              ${isUser
                                ? "bg-blue-600 text-white rounded-tr-none shadow-sm ml-auto max-w-fit"
                                : isError
                                    ? "bg-red-50 border border-red-100 text-red-800 rounded-tl-none w-fit"
                                    : "bg-white border border-gray-200 shadow-sm text-gray-700 rounded-tl-none w-fit"}`}
                        >
                            {formatContent(content)}
                        </div>
                    )}

                    {/* Generated Plotly Chart */}
                    {plotJson && !isUser && (
                        <div className="w-full">
                            <ChartRenderer plotJsonStr={plotJson} />
                        </div>
                    )}

                    {/* Reasoning Accordion */}
                    {reasoning && !isUser && !isError && (
                        <div className="w-full">
                            <button
                                onClick={() => setShowReasoning(!showReasoning)}
                                className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 transition-colors font-medium ml-1 mb-1"
                            >
                                <Lightbulb size={13} className={showReasoning ? "fill-purple-100" : ""} />
                                {showReasoning ? "Hide reasoning" : "How I figured this out"}
                            </button>
                            {showReasoning && (
                                <div className="text-xs text-gray-500 bg-purple-50/50 border border-purple-100/50 rounded-xl p-4 leading-relaxed mt-1">
                                    {reasoning}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Generated Code */}
                    {code && !isUser && (
                        <div className="w-full max-w-full">
                            <CodeBlock code={code} language="python" />
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}
