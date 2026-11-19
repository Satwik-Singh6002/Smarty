import os
import sys
import asyncio
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from openrouter_client import OpenRouterClient

load_dotenv()

models_to_test = [
    "arcee-ai/trinity-large-preview:free",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
    "openai/gpt-oss-20b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free"
]

async def test_models():
    b64_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    
    for model in models_to_test:
        client = OpenRouterClient(model=model)
        try:
            print(f"Testing {model}...")
            response = await client.chat(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ]
                }],
                max_tokens=20
            )
            print(f"SUCCESS {model}: {response.get('content')}")
        except Exception as e:
            print(f"FAILED {model}: {e}")

if __name__ == "__main__":
    asyncio.run(test_models())

