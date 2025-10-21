export interface DatasetInfo {
  name: string;
  description: string;
  task_type: string;
}

export interface Example {
  dataset: string;
  prompt: string;
  system_prompt: string;
  choices: string[] | null;
  gold_answer: string;
  metadata?: Record<string, any>;
}

export interface EvaluateRequest {
  dataset: string;
  prompt: string;
  system_prompt: string;
  choices: string[] | null;
  gold_answer: string;
  model?: string;
}

export interface EvaluateResponse {
  dataset: string;
  prompt: string;
  gold_answer: string;
  predicted_answer: string;
  score: number;
  metric: string;
  details?: Record<string, any>;
}

export interface LoadModelRequest {
  model_name: string;
  vllm_url?: string;  // Optional: only for vLLM mode
}

export interface ModelInfo {
  model_name: string | null;
  vllm_url?: string | null;
  device?: string | null;
  backend?: string | null;
  loaded: boolean;
}

export interface ModelOption {
  name: string;
  display_name: string;
  description: string;
}
