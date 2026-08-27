import axios from 'axios';
import {
    ConnectRequest,
    ConnectResponse,
    LoadTableRequest,
    LoadTableResponse,
    NLQRequest,
    NLQResponse,
    DemoDatasetListResponse,
    DemoDatasetLoadResponse,
    ProcessResponse,
    AppConfig,
} from './types';
// Type-only import — erased at compile time, so no runtime cycle with workspaces.ts.
import type { SavedState, WorkspaceMeta, WorkspaceRecord } from './workspaces';
import { getApiBaseUrl } from './runtimeEnv';

// Resolved when this module first loads. In the browser that is after the
// inline script in app/layout.tsx has run, so the injected value wins.
const API_BASE_URL = getApiBaseUrl();

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const api = {
    // ConnectORS
    connectDatabase: async (data: ConnectRequest): Promise<ConnectResponse> => {
        const response = await apiClient.post<ConnectResponse>('/connectors/connect', data);
        return response.data;
    },
    getSchema: async () => {
        const response = await apiClient.get('/connectors/schema');
        return response.data;
    },
    loadTable: async (data: LoadTableRequest): Promise<LoadTableResponse> => {
        const response = await apiClient.post<LoadTableResponse>('/connectors/load-table', data);
        return response.data;
    },
    disconnectDatabase: async (connectionId: string): Promise<void> => {
        await apiClient.delete(`/connectors/${connectionId}`);
    },

    // DATA
    uploadFile: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post('/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },
    listDemoDatasets: async (): Promise<DemoDatasetListResponse> => {
        const response = await apiClient.get<DemoDatasetListResponse>('/demo/list');
        return response.data;
    },
    loadDemoData: async (datasetId: string = 'sales'): Promise<DemoDatasetLoadResponse> => {
        const response = await apiClient.get<DemoDatasetLoadResponse>('/demo/load', {
            params: { dataset_id: datasetId }
        });
        return response.data;
    },

    // ANALYSIS
    processData: async (filePath: string, sessionId?: string): Promise<ProcessResponse> => {
        const response = await apiClient.post<ProcessResponse>('/process', {
            file_path: filePath,
            session_id: sessionId,
        });
        return response.data;
    },
    naturalLanguageQuery: async (data: NLQRequest): Promise<NLQResponse> => {
        const response = await apiClient.post<NLQResponse>('/nlq', data);
        return response.data;
    },

    // EXPORT
    getExportUrl: (sessionId: string, format: 'html' | 'markdown' | 'csv') => {
        return `${API_BASE_URL}/export/${sessionId}/${format}`;
    },

    // WORKSPACES (server-side persistence)
    listWorkspaces: async (): Promise<{ workspaces: WorkspaceMeta[] }> => {
        const response = await apiClient.get<{ workspaces: WorkspaceMeta[] }>('/workspaces');
        return response.data;
    },
    getWorkspace: async (id: string): Promise<WorkspaceRecord> => {
        const response = await apiClient.get<WorkspaceRecord>(`/workspaces/${id}`);
        return response.data;
    },
    saveWorkspace: async (
        id: string,
        payload: { datasetName: string; filePath: string; createdAt: number; state: SavedState }
    ): Promise<WorkspaceMeta> => {
        const response = await apiClient.put<WorkspaceMeta>(`/workspaces/${id}`, payload);
        return response.data;
    },
    deleteWorkspace: async (id: string): Promise<void> => {
        await apiClient.delete(`/workspaces/${id}`);
    },

    // SESSIONS
    createShareLink: async (sessionId: string, sessionData: unknown) => {
        const response = await apiClient.post('/sessions/share', { session_id: sessionId, session_data: sessionData });
        return response.data;
    },
    getSharedSession: async (token: string) => {
        const response = await apiClient.get(`/sessions/shared/${token}`);
        return response.data;
    },

    // CONFIG (live LLM provider/model)
    getConfig: async (): Promise<AppConfig> => {
        const response = await apiClient.get<AppConfig>('/config');
        return response.data;
    },
    setConfig: async (update: { provider?: string; model?: string }): Promise<{ provider: string; model: string }> => {
        const response = await apiClient.post('/config', update);
        return response.data;
    },
};
