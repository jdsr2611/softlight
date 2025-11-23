import asyncio
from src.agent import app

async def main():
    task = input("Enter task (e.g., 'Log into Linear and create a project'): ")
    
    print("Starting Softlight Agent...")
    
    # Run the graph
    inputs = {"task": task, "scratchpad": []}
    await app.ainvoke(inputs)
    
    print("✅ Task Complete. Check /output folder.")

if __name__ == "__main__":
    asyncio.run(main())