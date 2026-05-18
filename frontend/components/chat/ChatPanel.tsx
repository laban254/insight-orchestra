"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { MessageBubble, MessageProps } from "./MessageBubble";
import { AgentPipeline, Agent } from "../agents/AgentPipeline";
import { PipelineBlock } from "../agents/PipelineBlock";

export function ChatPanel({ filePath }: { filePath: string }) {
    const [messages, setMessages] = useState<MessageProps[]>([
        {
            role: "assistant",
            content: "Dataset loaded successfully! I'm Insight Orchestra. What would you like to know about your data?"
        }
    ]);
    const [input,       setInput]       = useState("");
    const [isLoading,   setIsLoading]   = useState(false);
    const [queryDone,   setQueryDone]   = useState(false);
    const [liveAgents,  setLiveAgents]  = useState<Agent[]>([]);
    const [sessionId]                   = useState(() => Math.random().toString(36).substring(2, 9));
    const [pipelineKey, setPipelineKey] = useState(0);

    // Ref always holds the latest agents — safe to read in async submitQuery
    const agentsRef      = useRef<Agent[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isLoading]);

    const handleAgentsChange = (agents: Agent[]) => {
        agentsRef.current = agents;
        setLiveAgents([...agents]);
    };

    const getErrorMessage = (error: unknown) => {
        if (
            typeof error === "object" && error !== null &&
            "response" in error &&
            typeof (error as { response?: unknown }).response === "object"
        ) {
            const r = (error as { response?: { data?: { detail?: string } } }).response;
            return r?.data?.detail ?? "An unexpected error occurred.";
        }
        if (error instanceof Error) return error.message;
        return "An unexpected error occurred.";
    };

    const submitQuery = async (userQuery: string) => {
        if (!userQuery || isLoading) return;

        setInput("");
        setMessages(prev => [...prev, { role: "user", content: userQuery }]);
        setIsLoading(true);
        setQueryDone(false);
        setLiveAgents([]);
        agentsRef.current = [];
        setPipelineKey(k => k + 1);

        try {
            const response = await api.naturalLanguageQuery({
                file_path: filePath,
                question: userQuery,
                session_id: sessionId,
            });

            setMessages(prev => [...prev, {
                role: "assistant",
                content: response.answer,
                code: response.code,
                plotJson: response.plot_json,
                reasoning: response.reasoning,
                pipelineAgents: [...agentsRef.current],
            }]);
        } catch (error: unknown) {
            setMessages(prev => [...prev, {
                role: "assistant",
                content: getErrorMessage(error),
                isError: true,
                pipelineAgents: [...agentsRef.current],
            }]);
        } finally {
            setIsLoading(false);
            setQueryDone(true);
            setLiveAgents([]);
        }
    };

    return (
        <div className="flex flex-col h-full bg-gray-50/50 rounded-xl overflow-hidden border border-gray-200 shadow-xl">

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6">
                {messages.map((msg, idx) => (
                    <MessageBubble key={idx} {...msg} />
                ))}

                {/* Live pipeline pill — same collapsed style as after-done */}
                {isLoading && (
                    <div className="flex items-start gap-3 my-3">
                        <div className="w-8 h-8 rounded-full bg-purple-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 opacity-0">
                            {/* spacer to align with assistant avatar */}
                        </div>
                        <div className="flex-1 max-w-2xl pt-0.5">
                            <PipelineBlock agents={liveAgents} isRunning />
                        </div>
                    </div>
                )}

                {/* Hidden SSE listener — drives liveAgents + agentsRef */}
                <div className="hidden">
                    <AgentPipeline
                        key={pipelineKey}
                        sessionId={sessionId}
                        isDone={queryDone}
                        mode="nlq"
                        onAgentsChange={handleAgentsChange}
                    />
                </div>

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 bg-white border-t border-gray-200">
                <form
                    onSubmit={(e) => { e.preventDefault(); void submitQuery(input.trim()); }}
                    className="relative flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-2xl p-2 shadow-sm focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all"
                >
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                void submitQuery(input.trim());
                            }
                        }}
                        placeholder="Ask a question about your data…"
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
                    Insight Orchestra can make mistakes. Always review the generated code.
                </p>
            </div>
        </div>
    );
}
