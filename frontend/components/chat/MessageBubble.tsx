"use client";

import { MessageCircle, Bot } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { ChartRenderer } from "../viz/ChartRenderer";

export interface MessageProps {
    role: "user" | "assistant";
    content: string;
    code?: string | null;
    plotJson?: string | null;
}

export function MessageBubble({ role, content, code, plotJson }: MessageProps) {
    const isUser = role === "user";

    return (
        <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} my-4`}>
            <div className={`flex max-w-[85%] gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}>

                {/* Avatar */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1
          ${isUser ? "bg-blue-600 text-white" : "bg-purple-600 text-white"}`}
                >
                    {isUser ? <MessageCircle size={16} /> : <Bot size={16} />}
                </div>

                {/* Message Body */}
                <div className="flex flex-col gap-2 min-w-0">
                    {/* Text content */}
                    {content && (
                        <div className={`p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
              ${isUser
                                ? "bg-blue-600 text-white rounded-tr-none"
                                : "bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-none"}`}
                        >
                            {content}
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
