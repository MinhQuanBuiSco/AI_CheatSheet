import axios from 'axios';
import type {
  DatasetInfo,
  Example,
  EvaluateRequest,
  EvaluateResponse,
  LoadModelRequest,
  ModelInfo,
  ModelOption,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiClient = {
  // Get all available datasets
  getDatasets: async (): Promise<DatasetInfo[]> => {
    const response = await api.get<DatasetInfo[]>('/datasets');
    return response.data;
  },

  // Get all available model options
  getModels: async (): Promise<ModelOption[]> => {
    const response = await api.get<ModelOption[]>('/models');
    return response.data;
  },

  // Get a random example from a dataset
  getExample: async (datasetName: string): Promise<Example> => {
    const response = await api.get<Example>(`/datasets/${datasetName}/example`);
    return response.data;
  },

  // Evaluate a prediction
  evaluate: async (request: EvaluateRequest): Promise<EvaluateResponse> => {
    const response = await api.post<EvaluateResponse>('/evaluate', request);
    return response.data;
  },

  // Load a model
  loadModel: async (request: LoadModelRequest): Promise<ModelInfo> => {
    const response = await api.post<ModelInfo>('/model/load', request);
    return response.data;
  },

  // Get current model info
  getCurrentModel: async (): Promise<ModelInfo> => {
    const response = await api.get<ModelInfo>('/model/current');
    return response.data;
  },

  // Evaluate with streaming (using fetch for SSE support)
  evaluateStream: async (
    request: EvaluateRequest,
    onToken: (token: string) => void,
    onResult: (result: EvaluateResponse) => void,
    onError: (error: string) => void
  ): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/evaluate/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split('\n');
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'token') {
                onToken(data.content);
              } else if (data.type === 'result') {
                onResult(data as EvaluateResponse);
              } else if (data.type === 'error') {
                onError(data.message);
              } else if (data.type === 'done') {
                // Stream complete
                break;
              }
            } catch (parseError) {
              console.error('Failed to parse SSE data:', line, parseError);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      onError(error instanceof Error ? error.message : 'Unknown error');
    }
  },
};
