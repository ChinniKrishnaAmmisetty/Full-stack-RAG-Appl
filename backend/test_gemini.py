import asyncio
import os
import sys

# Ensure backend dir is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import google.generativeai as genai
from app.config import get_settings

async def test_gemini():
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY
    print(f"Loaded API Key: {api_key[:10]}...{api_key[-5:]} (Length: {len(api_key)})")
    
    genai.configure(api_key=api_key)
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        print("Model initialized. Testing generate_content...")
        response = model.generate_content("Say 'Hello world'")
        print(f"SUCCESS! Response: {response.text}")
    except Exception as e:
        print(f"FAILED!\nError Type: {type(e).__name__}\nError Details: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
