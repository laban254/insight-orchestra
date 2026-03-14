"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { MessageBubble, MessageProps } from "./MessageBubble";
import { AgentPipeline } from "../agents/AgentPipeline";

export function ChatPanel({ filePath }: { filePath: string }) {
    const [messages, setMessages] = useState<MessageProps[]>([
        {
            role: "assistant",
            content: "Dataset loaded successfully! I am Insight Orchestra. What would you like to know about your data?"
        }
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId] = useState(() => Math.random().toString(36).substring(2, 9));
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userQuery = input.trim();
        setInput("");

        // Add user message
        setMessages(prev => [...prev, { role: "user", content: userQuery }]);
        setIsLoading(true);

        try {
            const response = await api.naturalLanguageQuery({
                file_path: filePath,
                question: userQuery,
                session_id: sessionId
            });

            setMessages(prev => [...prev, {
                role: "assistant",
                content: response.answer,
                code: response.code,
                plotJson: response.plot_json
            }]);
        } catch (error: any) {
            setMessages(prev => [...prev, {
                role: "assistant",
                content: error.response?.data?.detail || error.message || "An unexpected error occurred",
                isError: true
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-gray-50/50 rounded-xl overflow-hidden border border-gray-200 shadow-xl">

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-24">
                {messages.map((msg, idx) => (
                    <MessageBubble key={idx} {...msg} />
                ))}

                {isLoading && (
                    <div className="flex items-start gap-4 my-4">
                        <div className="w-8 h-8 rounded-full bg-purple-600 text-white flex items-center justify-center flex-shrink-0 mt-1">
                            <Loader2 size={16} className="animate-spin" />
                        </div>
                        <div className="flex-1 max-w-2xl min-w-0">
                            <AgentPipeline sessionId={sessionId} />
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-white border-t border-gray-200">
                <form
                    onSubmit={handleSubmit}
                    className="relative max-w-4xl mx-auto flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-2xl p-2 shadow-sm focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all"
                >
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                        placeholder="Ask a question about your data..."
                        className="flex-1 max-h-32 min-h-[44px] bg-transparent resize-none outline-none py-3 px-4 text-sm text-gray-900 placeholder:text-gray-400"
                        rows={1}
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
                    >
                        {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                    </button>
                </form>
                <p className="text-center text-xs text-gray-400 mt-2">
                    Insight Orchestra Agents can make mistakes. Always review the code.
                </p>
            </div>
        </div>
    );
}
