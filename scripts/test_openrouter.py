import asyncio
from openrouter_client import OpenRouterClient
from text_chat_loop import TOOLS

async def main():
    print("Testing nemotron with tools")
    client = OpenRouterClient()
    try:
        response = await client.chat(
            messages=[{"role": "user", "content": "open YouTube"}],
            tools=TOOLS,
            max_tokens=200
        )
        import json
        print("Response received:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print("Error during chat:", e)

asyncio.run(main())
