import axios from 'axios';
import {
    ConnectRequest,
    ConnectResponse,
    LoadTableRequest,
    LoadTableResponse,
    DatabaseQueryRequest,
    DatabaseQueryResponse,
    NLQRequest,
    NLQResponse,
    DemoDatasetListResponse,
    DemoDatasetLoadResponse,
    ProcessResponse,
    AppConfig,
    UploadResponse,
    DatasetRowsResponse,
    TransformRequest,
    TransformResponse,
    LocalDatabaseFilesResponse,
} from './types';
// Type-only import — erased at compile time, so no runtime cycle with workspaces.ts.
import type { SavedState, WorkspaceMeta, WorkspaceRecord } from './workspaces';
import { getApiBaseUrl } from './runtimeEnv';

// Resolved when this module first loads. In the browser that is after the
// inline script in app/layout.tsx has run, so the injected value wins.
const API_BASE_URL = getApiBaseUrl();
// Every backend route except /health, /docs and /redoc lives under this
// versioned prefix (see backend/app/main.py).
const API_V1_URL = `${API_BASE_URL}/api/v1`;

const apiClient = axios.create({
    baseURL: API_V1_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    // Harmless when auth is off (no cookie exists to send); required once
    // AUTH_ENABLED=true so the io_session cookie rides along with every
    // request — without it every call would look unauthenticated.
    withCredentials: true,
});

// A 401 here only ever means "auth is on and this session is missing/expired"
// (every other deliberate error in the API is 400/404/409/500 with a string
// `detail`) — bounce to the login page rather than letting the caller render
// a broken, half-authenticated view.
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (
            error?.response?.status === 401 &&
            typeof window !== 'undefined' &&
            !window.location.pathname.startsWith('/login')
        ) {
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

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
    queryDatabase: async (data: DatabaseQueryRequest): Promise<DatabaseQueryResponse> => {
        const response = await apiClient.post<DatabaseQueryResponse>('/connectors/query', data);
        return response.data;
    },
    listLocalDatabaseFiles: async (): Promise<LocalDatabaseFilesResponse> => {
        const response = await apiClient.get<LocalDatabaseFilesResponse>('/connectors/local-files');
        return response.data;
    },
    disconnectDatabase: async (connectionId: string): Promise<void> => {
        await apiClient.delete(`/connectors/${connectionId}`);
    },

    // DATA
    uploadFile: async (file: File): Promise<UploadResponse> => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post<UploadResponse>('/upload', formData, {
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
    processData: async (datasetId: string, sessionId?: string): Promise<ProcessResponse> => {
        const response = await apiClient.post<ProcessResponse>('/process', {
            dataset_id: datasetId,
            session_id: sessionId,
        });
        return response.data;
    },
    getDataset: async (datasetId: string): Promise<UploadResponse> => {
        const response = await apiClient.get<UploadResponse>(`/datasets/${datasetId}`);
        return response.data;
    },
    getDatasetRows: async (
        datasetId: string,
        offset: number = 0,
        limit: number = 50
    ): Promise<DatasetRowsResponse> => {
        const response = await apiClient.get<DatasetRowsResponse>(`/datasets/${datasetId}/rows`, {
            params: { offset, limit },
        });
        return response.data;
    },
    transformDataset: async (
        datasetId: string,
        data: TransformRequest
    ): Promise<TransformResponse> => {
        const response = await apiClient.post<TransformResponse>(
            `/datasets/${datasetId}/transform`,
            data
        );
        return response.data;
    },
    naturalLanguageQuery: async (data: NLQRequest): Promise<NLQResponse> => {
        const response = await apiClient.post<NLQResponse>('/nlq', data);
        return response.data;
    },

    // EXPORT
    getExportUrl: (sessionId: string, format: 'html' | 'markdown' | 'csv') => {
        return `${API_V1_URL}/export/${sessionId}/${format}`;
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
        payload: { datasetName: string; datasetId: string; createdAt: number; state: SavedState }
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
