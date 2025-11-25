import asyncio
from src.agent import run_autonomous_agent

TASKS = {
    "1": {
        "name": "wikipedia_research",
        "prompt": "Go to wikipedia.org. Search for 'SpaceX'. Click on the 'History' section in the table of contents. keep scrolling untill you find an imageClick the first image you see."
    },
    "2": {
        "name": "saucedemo_checkout",
        "prompt": "Go to https://www.saucedemo.com/. Log in with user 'standard_user' and pass 'secret_sauce'. Add the backpack to cart. Click the cart icon."
    },
    "3": {
        "name": "linear_project_demo",
        "prompt": "Go to linear.app/login. Ask the user for login info if needed. Once logged in, navigate to Projects and click 'New Project'."
    },
    "4": {
        "name": "custom_task",
        "prompt": "CUSTOM"
    }
}

async def main():
    print("========================================")
    print("   SOFTLIGHT AGENT - DEMO RUNNER       ")
    print("========================================")
    print("1. Wikipedia Research (No Login)")
    print("2. SauceDemo E-Commerce (Auto Login)")
    print("3. Linear App (Requires Manual Login)")
    print("4. Custom Task")
    print("========================================")
    
    choice = input("Select a demo to run (1-4): ")
    
    if choice not in TASKS:
        print("Invalid choice.")
        return

    task_config = TASKS[choice]
    prompt = task_config["prompt"]
    name = task_config["name"]

    if choice == "4":
        prompt = input("Enter your custom task prompt: ")
        name = "custom_user_task"

    await run_autonomous_agent(prompt, name)

if __name__ == "__main__":
    asyncio.run(main())