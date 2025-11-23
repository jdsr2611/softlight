import os
import json
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv

# LangGraph & LangChain imports
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Import our tools
from src.browser import BrowserManager
from src.scribe import Scribe

load_dotenv()

# 1. Define the State (The Agent's Memory)
class AgentState(TypedDict):
    task: str
    plan: List[str]
    current_step_index: int
    scratchpad: List[str] # History of thoughts
    browser_state: dict   # The current accessibility tree
    finished: bool

# 2. Initialize the Tools
browser = BrowserManager(headless=False) # False so you can see it running!
scribe = Scribe()
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# --- The Node Functions (The Logic) ---

async def planner_node(state: AgentState):
    """
    Step 1: Look at the task and create a step-by-step plan.
    """
    print(f"🧠 Agent: Planning task '{state['task']}'...")
    
    prompt = f"""
    You are a QA Engineer Expert.
    User Task: {state['task']}
    
    Create a high-level, sequential plan to achieve this task on a generic web app.
    Return ONLY a JSON array of strings.
    Example: ["Navigate to URL", "Click Login", "Type Username", "Submit"]
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    # Simple parsing (in production, use Structured Output)
    try:
        # Clean generic markdown if present
        content = response.content.replace("```json", "").replace("```", "").strip()
        plan = json.loads(content)
    except:
        # Fallback
        plan = ["Navigate to App", "Perform Action"]
        
    print(f"📋 Plan created: {plan}")
    
    # Initialize Scribe
    scribe.start_task("web_app", state['task'], plan)
    
    # Start browser
    await browser.start()
    
    return {"plan": plan, "current_step_index": 0, "finished": False}

async def navigator_node(state: AgentState):
    """
    Step 2: The Loop. Look at the screen, look at the current step, and Act.
    """
    current_step = state['plan'][state['current_step_index']]
    print(f"\n🚀 Executing Step {state['current_step_index'] + 1}: {current_step}")
    
    # 1. Observe
    browser_state = await browser.get_current_state()
    
    # 2. Reason (Ask LLM what to do)
    # We give the LLM the 'Perception' (Accessibility Tree)
    elements_text = json.dumps(browser_state['interactive_elements'], indent=2)
    
    prompt = f"""
    Goal Step: {current_step}
    Current URL: {browser_state['url']}
    
    Visible Interactive Elements (Accessibility Tree):
    {elements_text}
    
    Decide the ONE next interaction.
    Return ONLY valid JSON:
    {{
        "action": "click" | "type" | "wait" | "done",
        "target_id": <int_id_from_list>,
        "text_content": "<text_if_typing>",
        "reasoning": "<why>"
    }}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content.replace("```json", "").replace("```", "").strip()
    decision = json.loads(content)
    
    print(f"🤖 Thought: {decision['reasoning']}")
    
    # 3. Capture & Act
    if decision['action'] == "done":
        return {"finished": True}
        
    if decision['action'] in ["click", "type"]:
        target_id = decision.get('target_id')
        
        # Visual Grounding: Highlight -> Screenshot -> Scribe
        bbox = await browser.highlight_element(target_id)
        await browser.page.screenshot(path="temp.png")
        
        scribe.capture_step(
            "temp.png", 
            browser_state, 
            decision, 
            bbox
        )
        
        # Physical Action
        await browser.perform_action(
            decision['action'], 
            target_id, 
            decision.get('text_content')
        )
        
        # Clean up highlight
        await browser.clear_highlights()

    # Move to next step logic (Simplified for demo)
    # In a real ReAct agent, we would stay on the same step until verified.
    # Here we just advance to keep the demo moving.
    new_index = state['current_step_index'] + 1
    finished = new_index >= len(state['plan'])
    
    return {"current_step_index": new_index, "finished": finished}

# --- Build the Graph ---

workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("navigator", navigator_node)

workflow.set_entry_point("planner")

workflow.add_edge("planner", "navigator")

# The Conditional Edge: Loop or End?
def should_continue(state):
    if state['finished']:
        return END
    return "navigator"

workflow.add_conditional_edges("navigator", should_continue)

app = workflow.compile()