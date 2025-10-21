from pydantic import BaseModel
from typing import Optional, Dict, Any


class DatasetInfo(BaseModel):
    name: str
    description: str
    task_type: str  # multiple_choice, code_generation, math, qa


class Example(BaseModel):
    dataset: str
    prompt: str
    system_prompt: str
    choices: Optional[list[str]] = None
    gold_answer: str
    metadata: Optional[Dict[str, Any]] = None


class EvaluateRequest(BaseModel):
    dataset: str
    prompt: str
    system_prompt: str
    choices: Optional[list[str]] = None
    gold_answer: str
    model: Optional[str] = None


class EvaluateResponse(BaseModel):
    dataset: str
    prompt: str
    gold_answer: str
    predicted_answer: str
    score: float
    metric: str
    details: Optional[Dict[str, Any]] = None


class LoadModelRequest(BaseModel):
    model_name: str
    vllm_url: Optional[str] = None  # Optional: only needed for vLLM mode


class ModelInfo(BaseModel):
    model_name: Optional[str] = None
    vllm_url: Optional[str] = None
    device: Optional[str] = None
    backend: Optional[str] = None  # "huggingface" or "vllm"
    loaded: bool = False
