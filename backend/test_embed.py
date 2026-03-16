import google.generativeai as genai
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.config import get_settings

s = get_settings()
genai.configure(api_key=s.GEMINI_API_KEY)
r = genai.embed_content(model=f"models/{s.GEMINI_EMBEDDING_MODEL}", content="test")
print(f"Dimension: {len(r['embedding'])}")
