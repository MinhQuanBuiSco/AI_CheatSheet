from typing import Optional
from openai import OpenAI
import os


class VLLMClient:
    """Client for interacting with vLLM server"""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.model_name: Optional[str] = None
        self.vllm_url: Optional[str] = None
        self.mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"

    def load_model(self, model_name: str, vllm_url: str):
        """
        Configure client to use a specific vLLM endpoint
        Note: vLLM server should already be running with the model loaded
        """
        self.vllm_url = vllm_url
        self.model_name = model_name

        if self.mock_mode:
            # In mock mode, just mark as loaded without connecting
            self.client = "MOCK"  # Dummy value to indicate loaded
            print(f"🧪 MOCK MODE: Model '{model_name}' loaded (simulated)")
        else:
            # Initialize OpenAI client pointing to vLLM server
            self.client = OpenAI(
                base_url=f"{vllm_url}/v1",
                api_key="EMPTY"  # vLLM doesn't require API key
            )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        stop: Optional[list[str]] = None
    ) -> str:
        """Generate response from the loaded model"""
        if self.client is None:
            raise RuntimeError("No model loaded. Call load_model first.")

        if self.mock_mode:
            # Mock mode: return simulated responses
            return self._generate_mock_response(prompt)

        try:
            response = self.client.completions.create(
                model=self.model_name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop
            )

            return response.choices[0].text.strip()

        except Exception as e:
            raise RuntimeError(f"Error generating response: {str(e)}")

    def _generate_mock_response(self, prompt: str) -> str:
        """Generate a mock response for testing without vLLM"""
        import random

        # Detect multiple choice questions
        if any(letter in prompt for letter in [" A.", " B.", " C.", " D."]):
            # Return a random letter for multiple choice
            choices = ["A", "B", "C", "D"]
            return random.choice(choices)

        # Detect math questions
        if any(word in prompt.lower() for word in ["calculate", "math", "number", "what is"]):
            # Return a random number
            return str(random.randint(1, 100))

        # Detect code questions
        if any(word in prompt.lower() for word in ["def ", "function", "return", "code"]):
            # Return a simple code snippet
            return "def solution():\n    return True"

        # Default: return a generic answer
        return "This is a mock response for testing purposes."

    def is_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.client is not None

    def get_model_info(self) -> dict:
        """Get information about currently loaded model"""
        return {
            "model_name": self.model_name,
            "vllm_url": self.vllm_url,
            "loaded": self.is_loaded()
        }
