"""
Production Model Deployment and Serving
Enterprise-grade model deployment with monitoring, scaling, and optimization.
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict
import time
from datetime import datetime

import torch
import torch.nn as nn
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer,
    pipeline,
    TextGenerationPipeline
)
from peft import PeftModel
import onnx
import onnxruntime as ort
from optimum.onnxruntime import ORTModelForCausalLM
from optimum.bettertransformer import BetterTransformer
import triton_python_backend_utils as pb_utils

# For serving
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Monitoring
import psutil
from prometheus_client import Counter, Histogram, Gauge, start_http_server


@dataclass
class DeploymentConfig:
    """Configuration for model deployment."""
    
    # Model configuration
    model_path: str
    tokenizer_path: Optional[str] = None
    model_type: str = "huggingface"  # "huggingface", "onnx", "triton"
    
    # Optimization settings
    optimize_for_inference: bool = True
    use_better_transformer: bool = True
    use_torch_compile: bool = False  # PyTorch 2.0+
    enable_dynamic_batching: bool = True
    max_batch_size: int = 32
    
    # Generation settings
    default_max_length: int = 512
    default_temperature: float = 0.7
    default_top_p: float = 0.9
    default_top_k: int = 50
    
    # Serving configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 60
    
    # Resource management
    device: str = "auto"  # "auto", "cpu", "cuda"
    max_memory_gb: Optional[float] = None
    enable_cpu_offload: bool = False
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8001
    log_level: str = "INFO"
    
    # Caching
    enable_kv_cache: bool = True
    cache_size_gb: float = 2.0


class ModelOptimizer:
    """Model optimization for production deployment."""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def optimize_model(self, model: nn.Module, tokenizer) -> nn.Module:
        """Apply various optimizations to the model."""
        self.logger.info("Optimizing model for inference...")
        
        # Set to eval mode
        model.eval()
        
        # Apply BetterTransformer optimization
        if self.config.use_better_transformer:
            try:
                model = BetterTransformer.transform(model)
                self.logger.info("Applied BetterTransformer optimization")
            except Exception as e:
                self.logger.warning(f"Could not apply BetterTransformer: {e}")
                
        # Apply torch.compile (PyTorch 2.0+)
        if self.config.use_torch_compile and hasattr(torch, 'compile'):
            try:
                model = torch.compile(model, mode="reduce-overhead")
                self.logger.info("Applied torch.compile optimization")
            except Exception as e:
                self.logger.warning(f"Could not apply torch.compile: {e}")
                
        # Enable attention optimization
        if hasattr(model.config, 'use_cache'):
            model.config.use_cache = self.config.enable_kv_cache
            
        return model
        
    def export_to_onnx(self, model: nn.Module, tokenizer, output_path: str):
        """Export model to ONNX format for optimized inference."""
        self.logger.info("Exporting model to ONNX...")
        
        try:
            from optimum.onnxruntime import ORTModelForCausalLM
            
            # Export to ONNX
            ort_model = ORTModelForCausalLM.from_pretrained(
                self.config.model_path, 
                export=True
            )
            
            # Save ONNX model
            ort_model.save_pretrained(output_path)
            tokenizer.save_pretrained(output_path)
            
            self.logger.info(f"ONNX model exported to {output_path}")
            return ort_model
            
        except Exception as e:
            self.logger.error(f"ONNX export failed: {e}")
            return None
            
    def quantize_model(self, model_path: str, output_path: str):
        """Apply quantization for reduced memory and faster inference."""
        self.logger.info("Quantizing model...")
        
        try:
            from optimum.onnxruntime import ORTQuantizer
            from optimum.onnxruntime.configuration import AutoQuantizationConfig
            
            # Load model
            model = ORTModelForCausalLM.from_pretrained(model_path)
            
            # Configure quantization
            qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=True)
            quantizer = ORTQuantizer.from_pretrained(model)
            
            # Apply quantization
            quantizer.quantize(save_dir=output_path, quantization_config=qconfig)
            
            self.logger.info(f"Quantized model saved to {output_path}")
            
        except Exception as e:
            self.logger.error(f"Quantization failed: {e}")


class ProductionModelServer:
    """Production-ready model serving with monitoring and optimization."""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.setup_logging()
        self.setup_device()
        self.load_model()
        self.setup_monitoring()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_device(self):
        """Setup compute device."""
        if self.config.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = self.config.device
            
        self.logger.info(f"Using device: {self.device}")
        
        # Set memory limits if specified
        if self.config.max_memory_gb and self.device == "cuda":
            torch.cuda.set_per_process_memory_fraction(
                self.config.max_memory_gb / (torch.cuda.get_device_properties(0).total_memory / 1e9)
            )
            
    def load_model(self):
        """Load and optimize the model."""
        self.logger.info(f"Loading model from {self.config.model_path}")
        
        # Load tokenizer
        tokenizer_path = self.config.tokenizer_path or self.config.model_path
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        # Load model based on type
        if self.config.model_type == "onnx":
            self.model = ORTModelForCausalLM.from_pretrained(self.config.model_path)
        else:
            # Load PyTorch model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                low_cpu_mem_usage=True
            )
            
            # Apply optimizations
            if self.config.optimize_for_inference:
                optimizer = ModelOptimizer(self.config)
                self.model = optimizer.optimize_model(self.model, self.tokenizer)
                
        # Create generation pipeline
        self.generator = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if self.device == "cuda" else -1,
            batch_size=self.config.max_batch_size if self.config.enable_dynamic_batching else 1
        )
        
        self.logger.info("Model loaded and optimized successfully")
        
    def setup_monitoring(self):
        """Setup monitoring metrics."""
        if not self.config.enable_metrics:
            return
            
        # Prometheus metrics
        self.request_count = Counter('model_requests_total', 'Total model requests')
        self.request_duration = Histogram('model_request_duration_seconds', 'Request duration')
        self.active_requests = Gauge('model_active_requests', 'Active requests')
        self.memory_usage = Gauge('model_memory_usage_bytes', 'Memory usage')
        self.gpu_memory = Gauge('model_gpu_memory_bytes', 'GPU memory usage')
        
        # Start metrics server
        start_http_server(self.config.metrics_port)
        self.logger.info(f"Metrics server started on port {self.config.metrics_port}")
        
    def update_system_metrics(self):
        """Update system monitoring metrics."""
        if not self.config.enable_metrics:
            return
            
        # CPU and memory
        process = psutil.Process()
        self.memory_usage.set(process.memory_info().rss)
        
        # GPU memory
        if self.device == "cuda" and torch.cuda.is_available():
            gpu_memory = torch.cuda.memory_allocated()
            self.gpu_memory.set(gpu_memory)
            
    async def generate_text_async(self, 
                                 prompt: str,
                                 max_length: Optional[int] = None,
                                 temperature: Optional[float] = None,
                                 top_p: Optional[float] = None,
                                 top_k: Optional[int] = None,
                                 do_sample: bool = True) -> str:
        """Generate text asynchronously."""
        
        # Update metrics
        if self.config.enable_metrics:
            self.request_count.inc()
            self.active_requests.inc()
            
        start_time = time.time()
        
        try:
            # Set generation parameters
            generation_kwargs = {
                "max_length": max_length or self.config.default_max_length,
                "temperature": temperature or self.config.default_temperature,
                "top_p": top_p or self.config.default_top_p,
                "top_k": top_k or self.config.default_top_k,
                "do_sample": do_sample,
                "pad_token_id": self.tokenizer.eos_token_id,
                "return_full_text": False
            }
            
            # Generate text
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.generator(prompt, **generation_kwargs)
            )
            
            generated_text = result[0]["generated_text"]
            
            # Update metrics
            if self.config.enable_metrics:
                self.request_duration.observe(time.time() - start_time)
                self.update_system_metrics()
                
            return generated_text
            
        finally:
            if self.config.enable_metrics:
                self.active_requests.dec()
                
    def batch_generate(self, prompts: List[str], **kwargs) -> List[str]:
        """Generate text for multiple prompts in batch."""
        if not self.config.enable_dynamic_batching:
            return [self.generate_text_async(prompt, **kwargs) for prompt in prompts]
            
        # Process in batches
        results = []
        for i in range(0, len(prompts), self.config.max_batch_size):
            batch_prompts = prompts[i:i + self.config.max_batch_size]
            batch_results = self.generator(batch_prompts, **kwargs)
            results.extend([result[0]["generated_text"] for result in batch_results])
            
        return results


# FastAPI Models
class GenerationRequest(BaseModel):
    prompt: str
    max_length: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    do_sample: bool = True


class BatchGenerationRequest(BaseModel):
    prompts: List[str]
    max_length: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    do_sample: bool = True


class GenerationResponse(BaseModel):
    generated_text: str
    generation_time: float
    prompt_length: int
    generated_length: int


class BatchGenerationResponse(BaseModel):
    results: List[GenerationResponse]
    total_generation_time: float
    batch_size: int


def create_fastapi_app(model_server: ProductionModelServer) -> FastAPI:
    """Create FastAPI application for model serving."""
    
    app = FastAPI(
        title="Production LLM Serving API",
        description="Production-ready LLM serving with monitoring and optimization",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.post("/generate", response_model=GenerationResponse)
    async def generate_text(request: GenerationRequest):
        """Generate text from a prompt."""
        try:
            start_time = time.time()
            
            generated_text = await model_server.generate_text_async(
                prompt=request.prompt,
                max_length=request.max_length,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                do_sample=request.do_sample
            )
            
            generation_time = time.time() - start_time
            
            return GenerationResponse(
                generated_text=generated_text,
                generation_time=generation_time,
                prompt_length=len(request.prompt.split()),
                generated_length=len(generated_text.split())
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    @app.post("/batch_generate", response_model=BatchGenerationResponse)
    async def batch_generate_text(request: BatchGenerationRequest):
        """Generate text for multiple prompts."""
        try:
            start_time = time.time()
            
            generated_texts = model_server.batch_generate(
                prompts=request.prompts,
                max_length=request.max_length,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                do_sample=request.do_sample
            )
            
            total_time = time.time() - start_time
            
            results = []
            for prompt, generated_text in zip(request.prompts, generated_texts):
                results.append(GenerationResponse(
                    generated_text=generated_text,
                    generation_time=total_time / len(request.prompts),  # Approximate
                    prompt_length=len(prompt.split()),
                    generated_length=len(generated_text.split())
                ))
                
            return BatchGenerationResponse(
                results=results,
                total_generation_time=total_time,
                batch_size=len(request.prompts)
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "device": model_server.device,
            "model_path": model_server.config.model_path
        }
        
    @app.get("/metrics")
    async def get_metrics():
        """Get current metrics."""
        if not model_server.config.enable_metrics:
            return {"metrics": "disabled"}
            
        model_server.update_system_metrics()
        
        metrics = {
            "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
            "cpu_percent": psutil.cpu_percent(),
        }
        
        if model_server.device == "cuda" and torch.cuda.is_available():
            metrics.update({
                "gpu_memory_allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
                "gpu_memory_cached_mb": torch.cuda.memory_reserved() / 1024 / 1024,
                "gpu_utilization": torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
            })
            
        return metrics
        
    return app


def deploy_model(config: DeploymentConfig):
    """Deploy model with FastAPI server."""
    
    # Initialize model server
    model_server = ProductionModelServer(config)
    
    # Create FastAPI app
    app = create_fastapi_app(model_server)
    
    # Run server
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        workers=config.workers,
        timeout_keep_alive=config.timeout,
        log_level=config.log_level.lower()
    )


def main():
    """Main function for model deployment."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy LLM for Production Serving")
    parser.add_argument("--model-path", type=str, required=True, help="Path to trained model")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    parser.add_argument("--device", type=str, default="auto", help="Device (auto, cpu, cuda)")
    parser.add_argument("--optimize", action="store_true", help="Apply inference optimizations")
    parser.add_argument("--batch-size", type=int, default=8, help="Maximum batch size")
    parser.add_argument("--no-metrics", action="store_true", help="Disable monitoring")
    
    args = parser.parse_args()
    
    # Create deployment configuration
    config = DeploymentConfig(
        model_path=args.model_path,
        host=args.host,
        port=args.port,
        workers=args.workers,
        device=args.device,
        optimize_for_inference=args.optimize,
        max_batch_size=args.batch_size,
        enable_metrics=not args.no_metrics
    )
    
    # Deploy model
    deploy_model(config)


if __name__ == "__main__":
    main()