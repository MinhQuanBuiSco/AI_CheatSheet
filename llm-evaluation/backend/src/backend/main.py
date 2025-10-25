from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from backend.models import (
    DatasetInfo,
    Example,
    EvaluateRequest,
    EvaluateResponse,
    LoadModelRequest,
    ModelInfo
)
from backend.dataset_loader import DatasetLoader
from backend.evaluator import Evaluator
from backend.hf_client import HuggingFaceClient

app = FastAPI(
    title="LLM Evaluation API",
    description="API for evaluating LLMs on various benchmarks",
    version="0.1.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
dataset_loader = DatasetLoader()
evaluator = Evaluator()
model_client = HuggingFaceClient()

print("\n" + "="*60)
print("🤗 Hugging Face Mode - Using local model inference")
print("   Models will be downloaded and run locally")
print("="*60 + "\n")

# Popular model options
AVAILABLE_MODELS = [
    {
        "name": "meta-llama/Llama-2-7b-hf",
        "display_name": "Llama 2 7B",
        "description": "Meta's Llama 2 7B parameter model"
    },
    {
        "name": "meta-llama/Llama-2-13b-hf",
        "display_name": "Llama 2 13B",
        "description": "Meta's Llama 2 13B parameter model"
    },
    {
        "name": "meta-llama/Meta-Llama-3-8B",
        "display_name": "Llama 3 8B",
        "description": "Meta's Llama 3 8B parameter model"
    },
    {
        "name": "meta-llama/Meta-Llama-3.1-8B",
        "display_name": "Llama 3.1 8B",
        "description": "Meta's Llama 3.1 8B parameter model"
    },
    {
        "name": "mistralai/Mistral-7B-v0.1",
        "display_name": "Mistral 7B",
        "description": "Mistral AI 7B parameter model"
    },
    {
        "name": "mistralai/Mixtral-8x7B-v0.1",
        "display_name": "Mixtral 8x7B",
        "description": "Mistral AI Mixtral 8x7B MoE model"
    },
    {
        "name": "google/gemma-2b",
        "display_name": "Gemma 2B",
        "description": "Google's Gemma 2B parameter model"
    },
    {
        "name": "google/gemma-7b",
        "display_name": "Gemma 7B",
        "description": "Google's Gemma 7B parameter model"
    },
    {
        "name": "Qwen/Qwen2.5-7B",
        "display_name": "Qwen 2.5 7B",
        "description": "Alibaba's Qwen 2.5 7B parameter model"
    },
    {
        "name": "microsoft/phi-2",
        "display_name": "Phi-2",
        "description": "Microsoft's Phi-2 2.7B parameter model"
    },
]


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "LLM Evaluation API",
        "version": "0.1.0",
        "endpoints": {
            "/datasets": "List available datasets",
            "/datasets/{name}/example": "Get random example from dataset",
            "/evaluate": "Evaluate model prediction",
            "/evaluate/stream": "Evaluate model prediction with streaming",
            "/models": "List available model options",
            "/model/load": "Load a model",
            "/model/current": "Get current model info"
        }
    }


@app.get("/datasets", response_model=list[DatasetInfo])
def list_datasets():
    """Get list of available evaluation datasets"""
    return dataset_loader.list_datasets()


@app.get("/models")
def list_models():
    """Get list of available model options"""
    return AVAILABLE_MODELS


@app.get("/datasets/{dataset_name}/example", response_model=Example)
def get_dataset_example(dataset_name: str):
    """Get a random example from the specified dataset"""
    try:
        example = dataset_loader.get_example(dataset_name)
        return example
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading example: {str(e)}")


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate_prediction(request: EvaluateRequest):
    """
    Evaluate a model's prediction on a given prompt
    If model is specified in request, it will be used for generation
    """
    try:
        # Generate prediction if model is loaded
        if not model_client.is_loaded():
            raise HTTPException(
                status_code=400,
                detail="No model loaded. Please load a model first using /model/load"
            )

        # Generate prediction from model
        try:
            predicted_answer = model_client.generate(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                max_tokens=512,
                temperature=0.0
            )
        except Exception as e:
            import traceback
            print(f"Error generating prediction: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error generating prediction: {str(e)}"
            )

        # Evaluate the prediction
        try:
            score, metric, details = evaluator.evaluate(
                dataset=request.dataset,
                predicted=predicted_answer,
                gold=request.gold_answer,
                choices=request.choices
            )
        except Exception as e:
            import traceback
            print(f"Error evaluating prediction: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error evaluating prediction: {str(e)}"
            )

        return EvaluateResponse(
            dataset=request.dataset,
            prompt=request.prompt,
            gold_answer=request.gold_answer,
            predicted_answer=predicted_answer,
            score=score,
            metric=metric,
            details=details
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error during evaluation: {str(e)}")


@app.post("/evaluate/stream")
async def evaluate_prediction_stream(request: EvaluateRequest):
    """
    Stream model predictions as they are generated, then evaluate
    Returns Server-Sent Events (SSE) stream
    """
    try:
        # Check if model is loaded
        if not model_client.is_loaded():
            raise HTTPException(
                status_code=400,
                detail="No model loaded. Please load a model first using /model/load"
            )

        def generate():
            try:
                # Collect full prediction while streaming
                full_prediction = ""

                # Stream tokens (using sync generator, not async)
                for chunk in model_client.stream_generate(
                    prompt=request.prompt,
                    system_prompt=request.system_prompt,
                    max_tokens=512,
                    temperature=0.0
                ):
                    full_prediction += chunk
                    # Send token chunk immediately
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

                # Evaluate the full prediction
                score, metric, details = evaluator.evaluate(
                    dataset=request.dataset,
                    predicted=full_prediction,
                    gold=request.gold_answer,
                    choices=request.choices
                )

                # Send evaluation result
                result = {
                    'type': 'result',
                    'dataset': request.dataset,
                    'prompt': request.prompt,
                    'gold_answer': request.gold_answer,
                    'predicted_answer': full_prediction,
                    'score': score,
                    'metric': metric,
                    'details': details
                }
                yield f"data: {json.dumps(result)}\n\n"

                # Send done signal
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                import traceback
                print(f"Error in streaming: {str(e)}")
                print(traceback.format_exc())
                error_data = {
                    'type': 'error',
                    'message': str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error during streaming evaluation: {str(e)}")


@app.post("/model/load", response_model=ModelInfo)
def load_model(request: LoadModelRequest):
    """
    Load a Hugging Face model locally for inference
    The model will be downloaded from Hugging Face Hub if not already cached
    """
    try:
        model_client.load_model(model_name=request.model_name)
        info = model_client.get_model_info()
        return ModelInfo(**info)

    except Exception as e:
        import traceback
        print(f"Error loading model: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error loading model: {str(e)}")


@app.get("/model/current", response_model=ModelInfo)
def get_current_model():
    """Get information about the currently loaded model"""
    info = model_client.get_model_info()
    return ModelInfo(**info)


def main() -> None:
    """Entry point for running the server"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
