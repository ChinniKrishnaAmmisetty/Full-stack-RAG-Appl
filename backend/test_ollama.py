import asyncio
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import httpx

async def test_ollama():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check if Ollama is running
            r = await client.get("http://localhost:11434/api/tags")
            print(f"Ollama is running. Models: {[m['name'] for m in r.json().get('models', [])]}")

            # Test generation
            print("Testing llama3.1:8b generation...")
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": "Say hello in one sentence.",
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 50},
                },
                timeout=60.0,
            )
            r.raise_for_status()
            print(f"SUCCESS! Response: {r.json().get('response', 'No response')}")
    except httpx.ConnectError:
        print("FAILED: Cannot connect to Ollama. Run 'ollama serve' first.")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(test_ollama())
