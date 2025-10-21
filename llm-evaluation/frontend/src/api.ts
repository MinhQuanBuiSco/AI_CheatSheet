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
};
