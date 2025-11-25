Softlight Browser Agent

This repo implements Agent B – a browser execution agent – plus two ways to provide Agent A – a planner.

The system takes a high-level question like:

“How do I create a new project in Linear and name it Softlight Demo? Capture each important step.”

and turns it into:

A concrete browser task (Agent A), and

A sequence of real UI interactions in a live browser, with screenshots and metadata saved as a dataset (Agent B).

It is designed to generalize across different apps by using the accessibility tree, not hard-coded selectors or URLs.

High-Level Architecture

There are three main pieces:

1. Planner Agent (Agent A)

File: src/agent_planner.py

Accepts a high-level, user-friendly question.

Uses gpt-4o to rewrite it into a concrete browser task (e.g. “navigate to X, click Y, type Z…”).

Saves this plan as JSON under plans/<slug>.json:

{
  "user_question": "...",
  "agent_b_task_prompt": "Navigate to linear.app and..."
}


Calls Agent B with:

task_prompt (the concrete instruction)

task_name (a slug, used as folder name in output/).

This is the “front door” of the local multi-agent system.

2. Browser Agent (Agent B – Brain)

File: src/agent.py
Key function: run_autonomous_agent(task_prompt: str, task_name: str)

This is the reasoning / orchestration loop over the browser.

Initialize

Loads OPENAI_API_KEY from .env.

Creates an LLM client:

ChatOpenAI(model="gpt-4o", temperature=0)


Creates a BrowserTool instance (see below).

Starts a new Scribe task so all screenshots/metadata go into:

output/<timestamp>_<task_name>/


System Prompt & JSON Action Schema

Agent B is constrained to a small set of actions:

{
  "action": "navigate" | "click" | "type" | "ask_user" | "done",
  "id": <int>,
  "url": "<string>",
  "text": "<string>",
  "question": "<string>"
}


The prompt also instructs the model to:

Close popups, cookie banners, and other blocking modals.

Use the Visible Elements list (from the accessibility tree).

Fill key form fields (especially “name” / “title”) before pressing create/submit.

ReAct Loop

For up to max_steps:

Observe

state = await tool.get_state()
# state = { "url": "...", "elements": ["[1] button: …", "[2] textbox: …", ...] }


Think

Builds a prompt with:

The normalized task.

Last few actions.

Current URL.

Truncated element list.

Calls gpt-4o and parses the JSON response.

Act

navigate → tool.navigate(url)

click / type → tool.act(action, id, text)

ask_user → pauses in the terminal so you can provide info (email, code, etc.).

done → stop.

Each action triggers a screenshot & metadata capture via BrowserTool.act and Scribe.

3. BrowserTool (Agent B – Body)

File: src/tools.py
Class: BrowserTool

This is the low-level UI controller and dataset generator.

Persistent Chromium Profile
context = await self.playwright.chromium.launch_persistent_context(
    user_data_dir=self.user_data_dir,
    headless=False,
    slow_mo=1000,
    viewport={"width": 1280, "height": 720},
)


Uses a fixed user_data_dir under playwright_profiles/linear_profile/.

Stores cookies and localStorage there so apps like Linear stay logged in across runs after the first login.

First run: you may need to help with magic-link login.
Later runs: the same profile is reused.

get_state(): Accessibility-Based Element Map
state = await tool.get_state()
# -> { "url": ..., "elements": ["[1] button: …", "[2] textbox: …", ...] }


Calls page.accessibility.snapshot().

Traverses the tree and keeps elements that:

are interactive (button, link, textbox, combobox, menuitem), or

have an accessible name.

For each such node it:

Assigns an integer ID.

Resolves a Playwright locator with page.get_by_role(...).

Builds a label combining name, value, and description.

The result looks like:

[5] textbox: Project name
[12] button: Create project
[20] button: Accept all cookies


This list is what the LLM uses to act on non-URL states like modals and forms.

act(): Click / Type + Scribe Capture
async def act(self, action_type: str, target_id: int, text: str = None):
    # 1. Lookup locator by ID
    # 2. Take screenshot + bounding box
    # 3. Perform click or type


Visual grounding & capture

Check locator.is_visible() and locator.bounding_box().

Save a screenshot to:

<current_task_dir>/step_XXX.png


Call:

self.scribe.capture_step(
    screenshot_path,
    {"url": self.page.url},
    {"type": action_type, "target": target_id, "text": text},
    box,
)


Physical action

click → locator.click()

type → robust typing:

Try locator.fill(text).

If that fails (e.g. container div), fall back to:

await locator.click()
await self.page.keyboard.type(text)


Attempt keyboard.press("Enter") to submit the form where appropriate.

So every JSON decision from the LLM becomes a real browser action and a labeled screenshot.

MCP / Claude Integration (External Agent A)

File: src/server.py

For a full multi-agent setup, the same BrowserTool is exposed over MCP so Claude Desktop can act as Agent A.

Exposed tools:

start_browser(task_name: str | None)

navigate_to(url: str)

get_screen_state()

perform_action(action: str, target_id: int, text: str | None)

ask_user_for_help(question: str)

start_browser also initializes a Scribe task:

browser_tool.scribe.start_task("claude_agent", task_name, [])
# browser_tool.scribe.current_task_dir is used for screenshots


Example Claude Desktop config (claude_desktop_config.json):

{
  "mcpServers": {
    "softlight-agent": {
      "command": "E:\\Interview assignments\\softlight\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.server"],
      "cwd": "E:\\Interview assignments\\softlight",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "E:\\Interview assignments\\softlight"
      }
    }
  }
}


Then in Claude you can ask:

“Use the softlight-agent tools to open linear.app, create a new project named ‘Softlight Demo’, and capture each step.”

Claude (Agent A) calls the tools; BrowserTool + Scribe do the real UI work and dataset capture.

Repo Structure
softlight/
  pyproject.toml
  requirements.txt
  .env                     # OPENAI_API_KEY
  plans/                   # Agent A plans (JSON)
    create_a_new_project_in_linear_and_name.json
    ...
  output/                  # Scribe output (Agent B)
    20251124-..._create_a_new_project_in_linear_and_name/
      step_001.png
      step_002.png
      ...
      (metadata from Scribe)
  playwright_profiles/
    linear_profile/        # Persistent Chromium profile for Linear
  src/
    agent.py               # Browser Agent (Agent B brain / ReAct loop)
    agent_planner.py       # Local Planner (Agent A)
    tools.py               # BrowserTool (Agent B body, Playwright+Scribe)
    scribe.py              # Logging / dataset writer
    server.py              # MCP server (Claude integration)

Setup
1. Install Dependencies

Using uv:

uv sync
python -m playwright install chromium


Or using pip:

pip install -r requirements.txt
python -m playwright install chromium

2. Environment Variables

Create .env in the project root:

OPENAI_API_KEY=sk-...

Usage
Mode 1 – Local Multi-Agent (Planner A + Browser B)

This is the main demo mode.

uv run python -m src.agent_planner "How do I create a new project in Linear and name it Softlight Demo? Capture each important step for me."


Flow:

agent_planner.py (Agent A) rewrites the question into a concrete browser task and saves:

plans/create_a_new_project_in_linear_and_name.json


It calls:

run_autonomous_agent(task_prompt, "create_a_new_project_in_linear_and_name")


agent.py (Agent B) launches Chromium, runs the ReAct loop, and Scribe records screenshots into:

output/<timestamp>_create_a_new_project_in_linear_and_name/step_XXX.png


On the first Linear run, you may need to help with login when the agent uses ask_user. Thanks to the persistent profile, later runs should reuse the session.

Mode 2 – Direct Browser Agent (Agent B Only)

If you want to bypass the planner and give a concrete task manually (depending on how you wire __main__ in agent.py):

uv run python -m src.agent


(or call run_autonomous_agent from a small script) and change the hard-coded test task.

Mode 3 – Claude as Agent A (MCP)

Configure Claude Desktop with the MCP server (see snippet above).

Restart Claude Desktop.

In a new chat:

“Use the softlight-agent tools to open https://www.wikipedia.org
, search for ‘Robotics’, and capture each important UI state.”

Claude will:

Start src.server.

Call start_browser, navigate_to, get_screen_state, and perform_action.

Generate a dataset in output/claude_agent_<session>/step_XXX.png.

Dataset Layout

For each task/workflow you run, you get:

Plan (Agent A): plans/<slug>.json
Contains:

Original user question

Concrete task passed to Agent B.

UI state sequence (Agent B + Scribe):

output/20251124-002403_create_a_new_project_in_linear_and_name/
  step_001.png
  step_002.png
  step_003.png
  ...
  (metadata from Scribe per step)


Each step_XXX.png corresponds to one LLM decision (click or type) with URL, action type, target ID and bounding box logged.

Example Tasks

Some example prompts for agent_planner.py:

Linear

“How do I create a new project in Linear and name it ‘Softlight Demo’? Capture each important step for me.”

“How do I filter issues in Linear so that only my open issues are shown? Capture the full workflow.”

Wikipedia

“How do I search for ‘Robotics’ on Wikipedia and open the main article? Capture each main screen.”

TodoMVC

“How do I add a todo called ‘Softlight Demo’ in the React TodoMVC example and then mark it complete? Capture each UI state.”

Limitations / Future Work

Complex modals

On complex UIs (e.g. Linear’s “New project” modal), accessibility labels can be weak, so the model may repeatedly click the submit button instead of filling all fields. The system still captures all intermediate states; a human can complete the last step if needed.

Token / rate limits

The agent truncates the element list per step to avoid hitting gpt-4o tokens-per-minute limits. Further compression or smarter filtering of elements could make this even more robust.

Loop detection

A natural improvement is to detect repeated actions on the same element with no change in UI and automatically switch strategy (e.g., try a type action, or escalate with a more detailed ask_user).