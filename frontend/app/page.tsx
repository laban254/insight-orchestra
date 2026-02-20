"use client";

import { useState } from "react";
import { FileUpload } from "@/components/upload/FileUpload";
import { DatabaseConnect } from "@/components/upload/DatabaseConnect";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { Database, FileUp } from "lucide-react";

export default function Home() {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [uploadMode, setUploadMode] = useState<"file" | "db">("file");

  if (filePath) {
    return (
      <main className="h-screen w-full flex flex-col pt-16 bg-gray-50">
        <div className="fixed top-0 left-0 w-full h-16 bg-white border-b border-gray-200 px-6 flex items-center justify-between z-10 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
              io
            </div>
            <h1 className="font-semibold text-gray-900 tracking-tight text-lg">Insight Orchestra</h1>
          </div>
          <div className="text-sm px-3 py-1.5 bg-gray-100 text-gray-600 rounded-full font-medium shadow-inner">
            Session Active
          </div>
        </div>
        <div className="flex-1 w-full max-w-5xl mx-auto p-4 md:p-6 mb-4">
          <ChatPanel filePath={filePath} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-xl mx-auto">

        <div className="text-center mb-10 space-y-3">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center text-white font-bold text-3xl mx-auto mb-6 shadow-xl shadow-blue-600/20">
            io
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            Insight Orchestra
          </h1>
          <p className="text-gray-500 max-w-sm mx-auto">
            Connect your data and let specialized AI agents uncover the insights that matter.
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="flex border-b border-gray-200">
            <button
              onClick={() => setUploadMode("file")}
              className={`flex-1 py-4 text-sm font-medium flex items-center justify-center gap-2 transition-colors
                ${uploadMode === "file" ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50/50" : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"}`}
            >
              <FileUp size={16} /> Upload CSV
            </button>
            <button
              onClick={() => setUploadMode("db")}
              className={`flex-1 py-4 text-sm font-medium flex items-center justify-center gap-2 transition-colors
                ${uploadMode === "db" ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50/50" : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"}`}
            >
              <Database size={16} /> Connect Database
            </button>
          </div>

          <div className="p-8 pb-10">
            {uploadMode === "file" ? (
              <FileUpload onUploadSuccess={setFilePath} />
            ) : (
              <DatabaseConnect
                onConnectSuccess={(schema: any) => {
                  // In this implementation, the "connection" doesn't strictly yield a single "file".
                  // But for simplicity of integration, we stub it to trigger ChatPanel.
                  alert("Connected successfully! Starting chat mode...");
                  setFilePath("database-session");
                }}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
