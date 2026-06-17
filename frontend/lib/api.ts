import axios from 'axios';
import {
    ConnectRequest,
    ConnectResponse,
    NLQRequest,
    NLQResponse,
    DemoDatasetListResponse,
    DemoDatasetLoadResponse,
    ProcessResponse,
    AppConfig,
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
