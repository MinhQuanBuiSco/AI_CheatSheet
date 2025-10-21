"""
Quick test script to verify vLLM connection
Usage: python test_vllm.py
"""

from openai import OpenAI

# Configuration
VLLM_URL = "http://localhost:8001"
MODEL_NAME = "meta-llama/Llama-2-7b-hf"  # Change this to your model

print(f"Testing connection to vLLM at {VLLM_URL}...")
print(f"Model: {MODEL_NAME}")
print("-" * 50)

try:
    # Initialize client
    client = OpenAI(
        base_url=f"{VLLM_URL}/v1",
        api_key="EMPTY"
    )

    # Test prompt
    test_prompt = "What is 2+2? Answer:"

    print(f"\nSending test prompt: '{test_prompt}'")

    # Generate response
    response = client.completions.create(
        model=MODEL_NAME,
        prompt=test_prompt,
        max_tokens=50,
        temperature=0.0
    )

    result = response.choices[0].text.strip()

    print(f"\n✅ SUCCESS!")
    print(f"Response: {result}")
    print(f"\nYour vLLM server is working correctly!")

except Exception as e:
    print(f"\n❌ ERROR!")
    print(f"Failed to connect to vLLM: {str(e)}")
    print(f"\nPossible solutions:")
    print(f"1. Make sure vLLM server is running at {VLLM_URL}")
    print(f"2. Check that the model '{MODEL_NAME}' is loaded")
    print(f"3. Start vLLM with: python -m vllm.entrypoints.openai.api_server --model {MODEL_NAME} --port 8001")
