import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.tools import BrowserTool

load_dotenv()

async def run_agent(user_task: str):
    print("🧠 Agent: Waking up...")
    
    tool = BrowserTool()
    await tool.start()
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    tool.scribe.start_task("general_task", user_task, [])
    
    print("🧠 Agent: Starting Navigation Loop...")
    
    action_history = []

    # SYSTEM PROMPT: No hardcoded rules, just general instructions
    messages = [
        SystemMessage(content="""
        You are an autonomous UI agent.
        I will give you the User's Task, the Current URL, and Visible Elements.
        
        YOUR JOB:
        1. If the browser is blank (about:blank), NAVIGATE to the site needed for the task.
        2. If you are missing info (2FA, Search Query, Password), use 'ask_user'.
        3. If the task is finished, use 'done'.
        
        Output JSON only:
        {
            "action": "click" | "type" | "navigate" | "ask_user" | "done",
            "id": <int>, "text": <string>, "url": <string>, "question": <string>
        }
        """)
    ]

    # We DO NOT navigate here. We let the agent decide in the first loop.
    
    while True:
        # A. Observe
        state = await tool.get_state()
        elements_text = "\n".join(state['elements'])
        history_text = "\n".join([f"- {h}" for h in action_history[-3:]])
        
        # B. Reason
        prompt = f"""
        Goal: {user_task}
        Current URL: {state['url']}
        
        Recent History:
        {history_text}
        
        Visible Elements:
        {elements_text}
        
        What is the next move?
        """
        
        response = await llm.ainvoke(messages + [HumanMessage(content=prompt)])
        content = response.content.replace("```json", "").replace("```", "").strip()
        
        print(f"🤖 Agent decides: {content}")
        
        try:
            cmd = json.loads(content)
        except:
            continue
            
        if cmd.get('action') == "done":
            print("✅ Task Complete!")
            break

        # --- INTERACTION ---
        if cmd['action'] == "ask_user":
            print(f"\n❓ AGENT ASKS: {cmd.get('question')}")
            user_input = input(">> YOUR ANSWER: ")
            action_history.append(f"User answered: {user_input}")
            continue

        # --- ACTION ---
        if cmd['action'] == "navigate":
            await tool.navigate(cmd['url'])
            action_history.append(f"Navigated to {cmd['url']}")
            
        elif cmd['action'] in ["click", "type"]:
            result = await tool.act(cmd['action'], cmd.get('id'), cmd.get('text'))
            if cmd['action'] == "type":
                action_history.append(f"Typed '{cmd['text']}'")
            else:
                action_history.append(f"Clicked ID {cmd['id']}")
            
        await asyncio.sleep(2)

if __name__ == "__main__":
    # Dynamic Input
    task = input("Enter task (e.g. 'Go to Google and search for Cats'): ")
    asyncio.run(run_agent(task))