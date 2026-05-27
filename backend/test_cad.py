import asyncio
from cad_agent import CadAgent

async def main():
    agent = CadAgent()
    print("Testing CAD Agent with prompt: 'a simple cube'")
    result = await agent.generate_prototype("a simple cube")
    if result:
        print("Success! Generated STL size:", len(result.get("data", "")))
        print("File saved to:", result.get("file_path"))
    else:
        print("Failed to generate CAD model.")

if __name__ == "__main__":
    asyncio.run(main())
