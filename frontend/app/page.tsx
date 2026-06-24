"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Database, FileUp, Waypoints, PanelLeft, Download, Plus, Clock, Moon, Command, Share2 } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { useToast } from "@/lib/toast";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ModelSwitcher } from "@/components/ui/ModelSwitcher";
import { CostMeter } from "@/components/ui/CostMeter";
import { ExportMenu } from "@/components/ui/ExportMenu";
import { CommandPalette, Command as Cmd } from "@/components/ui/CommandPalette";
import { FileUpload } from "@/components/upload/FileUpload";
import { DatabaseConnect } from "@/components/upload/DatabaseConnect";
import { DatasetSelector } from "@/components/upload/DatasetSelector";
import { DatasetInfoPanel } from "@/components/upload/DatasetInfoPanel";
import { Workspace } from "@/components/workspace/Workspace";
import { HistoryDrawer } from "@/components/workspace/HistoryDrawer";
import { api } from "@/lib/api";
import { DemoDataset } from "@/lib/types";
import { exportReport } from "@/lib/exportReport";
import {
    listWorkspaces,
    loadWorkspace,
    deleteWorkspace as removeWorkspace,
    saveWorkspace,
    type SavedState,
    type WorkspaceMeta,
} from "@/lib/workspaces";

export interface DatasetInfo {
    name: string;
    type: "uploaded" | "demo";
    rows: number | string;
    columns: number | string;
    description?: string;
    use_cases?: string[];
}

const newId = () => Math.random().toString(36).substring(2, 11);

function Logo({ size = 8 }: { size?: number }) {
    return (
        <div
            className="grid place-items-center rounded-xl bg-accent text-accent-fg glow-accent"
            style={{ width: `${size * 4}px`, height: `${size * 4}px` }}
        >
            <Waypoints size={size * 2.2} />
        </div>
    );
}

export default function Home() {
    const theme = useTheme();
    const toast = useToast();

    const [filePath, setFilePath] = useState<string | null>(null);
    const [datasetInfo, setDatasetInfo] = useState<DatasetInfo | null>(null);
    const [uploadMode, setUploadMode] = useState<"file" | "db">("file");
    const [availableDatasets, setAvailableDatasets] = useState<Record<string, DemoDataset> | null>(null);

    const [workspaceId, setWorkspaceId] = useState<string | null>(null);
    const [restore, setRestore] = useState<SavedState | null>(null);
    const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([]);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [paletteOpen, setPaletteOpen] = useState(false);
    const [cost, setCost] = useState({ tokens: 0, cost: 0 });

    const currentState = useRef<SavedState | null>(null);
    const createdAt = useRef<number>(Date.now());

    useEffect(() => {
        api.listDemoDatasets()
            .then((r) => setAvailableDatasets(r.datasets))
            .catch((e) => console.error("Failed to load datasets:", e));
        setWorkspaces(listWorkspaces());
    }, []);

    const startWorkspace = (path: string, info: DatasetInfo) => {
        setFilePath(path);
        setDatasetInfo(info);
        setWorkspaceId(newId());
        setRestore(null);
        currentState.current = null;
        createdAt.current = Date.now();
        setCost({ tokens: 0, cost: 0 });
    };

    const handleUploadSuccess = (path: string, info: DatasetInfo) => startWorkspace(path, info);

    const handleNew = () => {
        setFilePath(null);
        setDatasetInfo(null);
        setWorkspaceId(null);
        setRestore(null);
        currentState.current = null;
        setHistoryOpen(false);
    };

    const handleSwitchDataset = async (datasetId: string) => {
        try {
            const result = await api.loadDemoData(datasetId);
            startWorkspace(result.file_path, {
                name: result.dataset_name,
                type: "demo",
                rows: result.row_count,
                columns: result.column_count,
                description: result.description,
                use_cases: result.use_cases,
            });
        } catch {
            toast("Failed to load dataset", "error");
        }
    };

    const onPersist = useCallback(
        (state: SavedState) => {
            if (!workspaceId) return;
            currentState.current = state;
            const existing = listWorkspaces().find((w) => w.id === workspaceId);
            saveWorkspace(
                {
                    id: workspaceId,
                    datasetName: datasetInfo?.name ?? "Dataset",
                    filePath: filePath ?? "",
                    createdAt: existing?.createdAt ?? createdAt.current,
                },
                state
            );
            setWorkspaces(listWorkspaces());
        },
        [workspaceId, datasetInfo, filePath]
    );

    const reopen = (id: string) => {
        const record = loadWorkspace(id);
        if (!record) {
            toast("Could not load that analysis", "error");
            return;
        }
        const shape = record.state.analysisResult?.cleaner.report.final_shape;
        setFilePath(record.filePath);
        setDatasetInfo({
            name: record.datasetName,
            type: "demo",
            rows: shape ? shape[0] : "—",
            columns: shape ? shape[1] : "—",
        });
        setWorkspaceId(record.id);
        setRestore(record.state);
        currentState.current = record.state;
        createdAt.current = record.createdAt;
        setHistoryOpen(false);
    };

    const handleDelete = (id: string) => {
        removeWorkspace(id);
        setWorkspaces(listWorkspaces());
        if (id === workspaceId) handleNew();
    };

    const handleExport = useCallback(() => {
        const st = currentState.current;
        if (!st?.analysisResult) {
            toast("Run an analysis first", "info");
            return;
        }
        exportReport(datasetInfo?.name ?? "Dataset", st.analysisResult, st.results);
        toast("Report downloaded", "success");
    }, [datasetInfo, toast]);

    const handleShare = useCallback(async () => {
        const st = currentState.current;
        if (!st?.analysisResult || !workspaceId) {
            toast("Run an analysis first", "info");
            return;
        }
        try {
            const payload = {
                datasetName: datasetInfo?.name ?? "Dataset",
                analysisResult: st.analysisResult,
                results: st.results,
            };
            const { token } = await api.createShareLink(workspaceId, payload);
            const url = `${window.location.origin}/shared/${token}`;
            await navigator.clipboard.writeText(url);
            toast("Share link copied to clipboard", "success");
        } catch {
            toast("Could not create share link", "error");
        }
    }, [datasetInfo, workspaceId, toast]);

    // Command palette actions
    const commands: Cmd[] = [
        { id: "new", label: "New analysis", group: "actions", icon: Plus, run: handleNew },
        { id: "history", label: "Open history", group: "actions", icon: Clock, run: () => setHistoryOpen(true) },
        { id: "export", label: "Export report", group: "actions", icon: Download, run: handleExport },
        { id: "share", label: "Copy share link", group: "actions", icon: Share2, run: handleShare },
        { id: "theme", label: "Toggle dark / light", group: "actions", icon: Moon, run: theme.toggle },
        ...Object.entries(availableDatasets ?? {}).map(([id, ds]) => ({
            id: `ds-${id}`,
            label: `Open dataset: ${ds.name}`,
            group: "datasets",
            icon: Database,
            run: () => handleSwitchDataset(id),
        })),
    ];

    return (
        <>
            <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} commands={commands} />

            {filePath && workspaceId ? (
                <main className="flex h-screen w-full flex-col bg-bg">
                    <HistoryDrawer
                        open={historyOpen}
                        onClose={() => setHistoryOpen(false)}
                        workspaces={workspaces}
                        activeId={workspaceId}
                        onOpen={reopen}
                        onDelete={handleDelete}
                        onNew={handleNew}
                    />

                    <header className="relative z-30 flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border bg-surface/80 px-3 backdrop-blur md:px-4">
                        <div className="flex min-w-0 items-center gap-2">
                            <button
                                onClick={() => setHistoryOpen(true)}
                                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-fg"
                                title="History"
                            >
                                <PanelLeft size={16} />
                            </button>
                            <Logo size={8} />
                            <h1 className="hidden text-[15px] font-semibold tracking-tight text-fg sm:block">Insight Orchestra</h1>
                        </div>

                        <div className="flex min-w-0 items-center gap-1.5">
                            <button
                                onClick={() => setPaletteOpen(true)}
                                className="hidden items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs text-faint transition-colors hover:text-fg lg:flex"
                                title="Command palette"
                            >
                                <Command size={13} /> <kbd className="font-mono">⌘K</kbd>
                            </button>
                            <CostMeter tokens={cost.tokens} cost={cost.cost} />
                            <ModelSwitcher />
                            <button
                                onClick={handleShare}
                                className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-fg"
                                title="Share a read-only link"
                            >
                                <Share2 size={16} />
                            </button>
                            <ExportMenu sessionId={workspaceId} onReport={handleExport} />
                            <DatasetInfoPanel
                                info={datasetInfo}
                                onReset={handleNew}
                                onSwitch={handleSwitchDataset}
                                availableDatasets={availableDatasets}
                            />
                            <ThemeToggle />
                        </div>
                    </header>

                    <Workspace
                        key={workspaceId}
                        workspaceId={workspaceId}
                        filePath={filePath}
                        datasetName={datasetInfo?.name ?? "Dataset"}
                        restore={restore}
                        onPersist={onPersist}
                        onCost={(d) => setCost((c) => ({ tokens: c.tokens + d.tokens, cost: c.cost + d.cost }))}
                    />
                </main>
            ) : (
                <main className="relative flex min-h-screen items-center justify-center overflow-x-clip overflow-y-auto bg-bg p-4 py-10">
                    <div
                        aria-hidden
                        className="pointer-events-none absolute left-1/2 top-0 h-[420px] w-[820px] -translate-x-1/2 rounded-full opacity-30 blur-[120px]"
                        style={{ background: "radial-gradient(circle, var(--color-accent), transparent 70%)" }}
                    />
                    <div className="absolute right-4 top-4 flex items-center gap-2">
                        {workspaces.length > 0 && (
                            <button
                                onClick={() => setHistoryOpen(true)}
                                className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-muted transition-colors hover:text-fg"
                            >
                                <Clock size={14} /> History
                            </button>
                        )}
                        <ThemeToggle />
                    </div>

                    <HistoryDrawer
                        open={historyOpen}
                        onClose={() => setHistoryOpen(false)}
                        workspaces={workspaces}
                        activeId={null}
                        onOpen={reopen}
                        onDelete={handleDelete}
                        onNew={() => setHistoryOpen(false)}
                    />

                    <div className="relative z-10 mx-auto w-full max-w-xl">
                        <div className="mb-9 flex flex-col items-center text-center">
                            <div className="mb-6">
                                <Logo size={14} />
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-fg">Insight Orchestra</h1>
                            <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
                                Connect your data and let a team of specialized AI agents clean,
                                hypothesize, debate, and visualize the insights that matter.
                            </p>
                        </div>

                        <div className="rounded-2xl border border-border bg-surface shadow-[var(--shadow)]">
                            <div className="flex overflow-hidden rounded-t-2xl border-b border-border">
                                {([
                                    { id: "file", label: "Upload CSV", Icon: FileUp },
                                    { id: "db", label: "Connect Database", Icon: Database },
                                ] as const).map(({ id, label, Icon }) => {
                                    const active = uploadMode === id;
                                    return (
                                        <button
                                            key={id}
                                            onClick={() => setUploadMode(id)}
                                            className={`flex flex-1 items-center justify-center gap-2 py-4 text-sm font-medium transition-colors ${
                                                active
                                                    ? "border-b-2 border-accent text-accent"
                                                    : "border-b-2 border-transparent text-muted hover:text-fg"
                                            }`}
                                        >
                                            <Icon size={16} /> {label}
                                        </button>
                                    );
                                })}
                            </div>

                            <div className="p-6 sm:p-8">
                                {uploadMode === "file" ? (
                                    availableDatasets ? (
                                        <DatasetSelector onUploadSuccess={handleUploadSuccess} datasets={availableDatasets} />
                                    ) : (
                                        <FileUpload
                                            onUploadSuccess={(path) =>
                                                handleUploadSuccess(path, {
                                                    name: "Uploaded File",
                                                    type: "uploaded",
                                                    rows: "Unknown",
                                                    columns: "Unknown",
                                                })
                                            }
                                        />
                                    )
                                ) : (
                                    <DatabaseConnect
                                        onConnectSuccess={() =>
                                            handleUploadSuccess("database-session", {
                                                name: "Database Connection",
                                                type: "uploaded",
                                                rows: "N/A",
                                                columns: "N/A",
                                                description: "Connected to database",
                                            })
                                        }
                                    />
                                )}
                            </div>
                        </div>
                        <p className="mt-6 text-center text-xs text-faint">
                            Press <kbd className="rounded border border-border px-1 font-mono">⌘K</kbd> anytime · your data stays in your environment
                        </p>
                    </div>
                </main>
            )}
        </>
    );
}
