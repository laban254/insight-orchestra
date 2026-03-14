"use client";

import { MessageCircle, Bot } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { ChartRenderer } from "../viz/ChartRenderer";

export interface MessageProps {
    role: "user" | "assistant";
    content: string;
    code?: string | null;
    plotJson?: string | null;
    isError?: boolean;
}

export function MessageBubble({ role, content, code, plotJson, isError }: MessageProps) {
    const isUser = role === "user";

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

    return (
        <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} my-4`}>
            <div className={`flex max-w-[85%] gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}>

                {/* Avatar */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1
          ${isUser ? "bg-blue-600 text-white" : isError ? "bg-red-500 text-white" : "bg-purple-600 text-white"}`}
                >
                    {isUser ? <MessageCircle size={16} /> : isError ? <Bot size={16} /> : <Bot size={16} />}
                </div>

                {/* Message Body */}
                <div className="flex flex-col gap-2 min-w-0">
                    {/* Text content */}
                    {content && (
                        <div className={`p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
              ${isUser
                                ? "bg-blue-600 text-white rounded-tr-none"
                                : isError
                                    ? "bg-red-50 border border-red-100 text-red-800 rounded-tl-none"
                                    : "bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-none"}`}
                        >
                            {getErrorContent(content)}
                        </div>
                    )}

                    {/* Generated Plotly Chart */}
                    {plotJson && !isUser && (
                        <ChartRenderer plotJsonStr={plotJson} />
                    )}

                    {/* Generated Code */}
                    {code && !isUser && (
                        <CodeBlock code={code} language="python" />
                    )}
                </div>
            </div>
        </div>
    );
}
