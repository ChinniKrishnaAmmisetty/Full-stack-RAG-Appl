import asyncio
import os
import sys

# Ensure backend dir is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.services.rag_service import generate_rag_response

async def test_rag():
    try:
        # Use a dummy user_id that might not have a collection yet
        response = await generate_rag_response("test-user-123", "who is pavan kalyan")
        print(f"RESPONSE:\n{response}")
    except Exception as e:
        print(f"FATAL ERROR:\n{e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
