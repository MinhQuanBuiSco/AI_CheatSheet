"""
Hugging Face Transformers client for local model inference
"""
from typing import Optional, Iterator
import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer


class HuggingFaceClient:
    """Client for running inference with Hugging Face models locally"""

    def __init__(self):
        self.model: Optional[AutoModelForCausalLM] = None
        self.tokenizer: Optional[AutoTokenizer] = None
        self.model_name: Optional[str] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self, model_name: str):
        """
        Load a Hugging Face model locally
        Args:
            model_name: HuggingFace model identifier (e.g., 'microsoft/phi-2')
        """
        self.model_name = model_name

        try:
            print(f"📥 Loading model '{model_name}' from Hugging Face...")
            print(f"   Device: {self.device}")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )

            # Set pad token if not exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # Load model with appropriate dtype
            if self.device == "cuda":
                # Use float16 for GPU to save memory
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )
            else:
                # Use float32 for CPU
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    trust_remote_code=True
                )
                self.model = self.model.to(self.device)

            print(f"✅ Model '{model_name}' loaded successfully!")

        except Exception as e:
            raise RuntimeError(f"Error loading model: {str(e)}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        system_prompt: str = ""
    ) -> str:
        """Generate response from the loaded model"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("No model loaded. Call load_model first.")

        try:
            # Combine system prompt and user prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt

            # Tokenize input
            inputs = self.tokenizer(
                full_prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self.device)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else 1.0,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

            # Decode output
            generated_text = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )

            return generated_text.strip()

        except Exception as e:
            raise RuntimeError(f"Error generating response: {str(e)}")

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        system_prompt: str = ""
    ) -> Iterator[str]:
        """Generate response from the loaded model with streaming"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("No model loaded. Call load_model first.")

        try:
            # Combine system prompt and user prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt

            # Tokenize input
            inputs = self.tokenizer(
                full_prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self.device)

            # Create streamer
            streamer = TextIteratorStreamer(
                self.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True
            )

            # Generation kwargs
            generation_kwargs = {
                **inputs,
                "max_new_tokens": max_tokens,
                "temperature": temperature if temperature > 0 else 1.0,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer,
            }

            # Run generation in a separate thread
            thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
            thread.start()

            # Yield tokens as they are generated
            for text in streamer:
                yield text

            thread.join()

        except Exception as e:
            raise RuntimeError(f"Error generating response: {str(e)}")

    def is_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.model is not None

    def get_model_info(self) -> dict:
        """Get information about currently loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "huggingface"
        }

    def unload_model(self):
        """Unload the current model to free memory"""
        if self.model is not None:
            del self.model
            del self.tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        self.model = None
        self.tokenizer = None
        self.model_name = None
        print("🗑️  Model unloaded")
