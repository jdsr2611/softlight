import asyncio
import json
import os
import re
import sys
import argparse
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.tools import BrowserTool


# 1. Load API Keys
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not found in .env")
    print("Please create a .env file with your key.")
    sys.exit(1)


async def run_autonomous_agent(task_prompt: str, task_name: str):
    """
    Main Agent Loop.
    Input:
        task_prompt: free-form user instruction
        task_name: slug for saving screenshots / metadata to disk
    Output:
        Navigates browser, captures data, saves to /output folder via BrowserTool.scribe
    """
    print(f"\n🚀 STARTING TASK: {task_name}")
    print(f"📋 Prompt: {task_prompt}")

    # 2. Initialize the Body (Tools)
    tool = BrowserTool()

    # IMPORTANT: task-specific output folder
    tool.scribe.start_task("cli_runner", task_name, [])
    print(f"📂 Output will be saved to: {tool.scribe.current_task_dir}")

    # 3. Initialize the Brain (LLM)
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # 4. Start the Browser
    await tool.start()

    # 5. System personality & strict JSON API
    action_history = []
    messages = [
        SystemMessage(
            content="""
You are an autonomous Browser Agent.

HIGH-LEVEL GOAL:
- Given a natural language TASK, you must complete it in a real browser.
- You do NOT know the website structure in advance.
- You control the browser ONLY through a JSON command API.

TOOLS YOU HAVE:
1. navigate(url: string)
   - Open or change the current URL.

2. click(id: int)
   - Click one of the visible elements by its integer ID.

3. type(id: int, text: string)
   - Type text into an input/textarea element by ID.

4. ask_user(question: string)
   - If you are blocked by login, 2FA, or missing credentials, ask for help.

5. done
   - When you believe the TASK is fully completed, use action "done".

INPUTS YOU SEE EACH STEP:
- CURRENT URL
- HISTORY of your last few actions
- VISIBLE UI ELEMENTS: a numbered list like:
    [0] "Create project" (button)
    [1] "Email" (input)
    [2] "Accept all cookies" (button)
  Each element has an ID you can pass to click/type.

CRITICAL RULES:
- If CURRENT URL is blank (about:blank) and the TASK mentions a site
  (e.g. "Linear", "Notion", "Wikipedia"), first NAVIGATE to that site.
- You MUST always choose an action that moves the task forward.
- NEVER hallucinate IDs. Only use IDs that appear in the VISIBLE UI ELEMENTS list.

POPUP / MODAL HANDLING (VERY IMPORTANT):
- At every step, before continuing the main task, scan the VISIBLE UI ELEMENTS
  for anything like "Accept", "Reject", "Close", "×", "Skip", "Dismiss",
  "No thanks", cookie banners, newsletter signup, or donation popups.
- If such an element exists and looks like a banner, popup, or modal:
  - First, CLICK the best "close / reject / skip" button.
  - Only after that, continue with the main task.
- This is especially important on first page load.

NON-URL STATES (MODALS, FORMS, etc.):
- Many important states (create modals, forms, success messages) do NOT change the URL.
- You SHOULD still:
  - Click the right buttons
  - Fill the right fields
  - Consider those as steps toward "done"
- You do NOT need URLs for these; rely on element labels and roles.

- When you open any creation or form modal (e.g. "Create", "New", "Submit", "Save"),
  ALWAYS look for textboxes whose labels include words like "name" or "title", and
  FILL them with the required values (for example, "Softlight Demo") before clicking
  the final "Create"/"Submit"/"Save" button.

WHEN TO FINISH:
- Use action "done" ONLY when:
  - The task goal is clearly achieved (e.g. project created, filter applied, setting changed).
- Your JSON can be:
  { "action": "done", "id": null, "text": null, "url": null, "question": "Short summary of what you accomplished." }

OUTPUT FORMAT (MANDATORY):
You MUST return a SINGLE JSON object and NOTHING else. No prose.

JSON SCHEMA:
{
  "action": "click" | "type" | "navigate" | "ask_user" | "done",
  "id":   <int or null>,
  "text": <string or null>,
  "url":  <string or null>,
  "question": <string or null>
}
"""
        )
    ]

    step_count = 0
    max_steps = 25

    # 6. ReAct Loop (Reason + Act)
    while step_count < max_steps:
        step_count += 1

        # A. OBSERVE
        state = await tool.get_state()

        max_elements = 80  # or even 50 for safety
        visible_elements = state["elements"][:max_elements]

        elements_text = "\n".join(visible_elements)
        if len(state["elements"]) > max_elements:
            elements_text += f"\n... ({len(state['elements']) - max_elements} more elements truncated) ..."


        # B. REASON
        prompt = f"""
TASK: {task_prompt}

CURRENT URL: {state['url']}

HISTORY (Last 5 actions):
{action_history[-5:]}

VISIBLE UI ELEMENTS:
{elements_text}

Decide the SINGLE next action. 
Remember:
- Close/dismiss popups first, if present.
- Then continue working toward completing the TASK.
Return ONLY valid JSON according to the schema.
"""

        print(f"\n🧠 Thinking... (Step {step_count})")

        try:
            response = await llm.ainvoke(messages + [HumanMessage(content=prompt)])
            content = (
                response.content.replace("```json", "")
                .replace("```", "")
                .strip()
            )
            cmd = json.loads(content)

            # Pretty print what we decided
            desc = f"{cmd.get('action', '').upper()}"
            if cmd.get("url"):
                desc += f" -> {cmd['url']}"
            if cmd.get("text"):
                desc += f" -> '{cmd['text']}'"
            if cmd.get("id") is not None:
                desc += f" (ID: {cmd['id']})"
            print(f"🤖 Action: {desc}")

        except Exception as e:
            msg = str(e)
            print(f"⚠️ Error calling LLM: {msg}")
            if "rate_limit_exceeded" in msg or "tokens per min" in msg:
                print("⛔ Hit OpenAI TPM limit; stopping this run early. Partial dataset is still saved.")
                break
            continue

        # C. ACT
        action = cmd.get("action")

        if action == "done":
            print("✅ Agent signal: Task Complete.")
            summary = cmd.get("question") or cmd.get("text")
            if summary:
                print(f"📝 Summary: {summary}")
            break

        if action == "ask_user":
            print(f"\n❓ AGENT NEEDS HELP: {cmd.get('question')}")
            user_input = input(">> Your Answer: ")
            action_history.append(f"User answered: {user_input}")
            continue

        if action == "navigate":
            url = cmd.get("url")
            if not url:
                print("⚠️ 'navigate' action missing URL, skipping.")
            else:
                await tool.navigate(url)
                action_history.append(f"Navigated to {url}")

        elif action in ["click", "type"]:
            elem_id = cmd.get("id")
            text = cmd.get("text")
            if elem_id is None:
                print("⚠️ 'click'/'type' action missing element ID, skipping.")
            else:
                await tool.act(action, elem_id, text)
                action_history.append(f"Performed {action} on ID {elem_id} (text={text})")

        # Allow the page to update
        await asyncio.sleep(2)

    print("🎉 Session Finished. Check /output for the dataset.")


def _slugify_task_name(text: str) -> str:
    """
    Turn a free-form task prompt into a filesystem-friendly slug.
    """
    text = text.lower().strip()
    # Limit to first ~8 words
    words = text.split()
    text = " ".join(words[:8])
    slug = re.sub(r"[^a-z0-9]+", "_", text)
    slug = slug.strip("_")
    return slug or "task"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the autonomous browser agent on an arbitrary task."
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Task description, e.g. 'Create a new project in Linear and name it Test Agent'.",
    )
    parser.add_argument(
        "-n",
        "--name",
        help="Optional task name / slug for output folder.",
    )

    args = parser.parse_args()

    if args.prompt:
        task_prompt = " ".join(args.prompt)
    else:
        # Fallback: interactive input
        task_prompt = input("Describe the task for the browser agent:\n> ").strip()

    if not task_prompt:
        print("❌ No task prompt provided. Exiting.")
        sys.exit(1)

    task_name = args.name or _slugify_task_name(task_prompt)

    asyncio.run(run_autonomous_agent(task_prompt, task_name))
