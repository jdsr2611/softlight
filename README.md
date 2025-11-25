# Softlight Browser Agent

![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Softlight** is a robust browser execution agent system designed to bridge high-level user intent with concrete browser actions. It implements a dual-agent architecture:
- **Agent A (Planner):** Translates high-level questions into structured browser tasks.
- **Agent B (Executor):** Executes tasks in a live browser using accessibility-tree-based navigation, capturing a rich dataset of interactions.

The system is designed to generalize across different web applications by relying on the accessibility tree rather than brittle, hard-coded selectors.

---

## 📋 Table of Contents

- [Architecture](#-architecture)
  - [1. Planner Agent (Agent A)](#1-planner-agent-agent-a)
  - [2. Browser Agent (Agent B)](#2-browser-agent-agent-b--brain)
  - [3. BrowserTool](#3-browsertool-agent-b--body)
  - [MCP / Claude Integration](#mcp--claude-integration)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#-usage)
  - [Mode 1: Local Multi-Agent](#mode-1--local-multi-agent-planner-a--browser-b)
  - [Mode 2: Direct Browser Agent](#mode-2--direct-browser-agent-agent-b-only)
  - [Mode 3: Claude as Agent A (MCP)](#mode-3--claude-as-agent-a-mcp)
- [Dataset Layout](#-dataset-layout)
- [Example Tasks](#-example-tasks)
- [Limitations & Future Work](#-limitations--future-work)

---

## 🏗 Architecture

The system consists of three main components working in unison.

### 1. Planner Agent (Agent A)
**File:** `src/agent_planner.py`

The Planner serves as the entry point. It accepts a high-level user question and uses **GPT-4o** to decompose it into a concrete browser task.

- **Input:** "How do I create a new project in Linear...?"
- **Output:** A JSON plan saved in `plans/<slug>.json`.
- **Action:** Calls Agent B with a specific `task_prompt` and `task_name`.

### 2. Browser Agent (Agent B – Brain)
**File:** `src/agent.py`

This component runs the reasoning and orchestration loop (ReAct) over the browser.

- **Initialization:** Loads API keys, creates an LLM client (`ChatOpenAI`), and initializes `BrowserTool`.
- **ReAct Loop:**
  1.  **Observe:** Captures the current state (URL, accessibility tree).
  2.  **Think:** specifices the next action (`navigate`, `click`, `type`, `ask_user`, `done`) based on the task and history.
  3.  **Act:** Executes the action via `BrowserTool`.

### 3. BrowserTool (Agent B – Body)
**File:** `src/tools.py`

The low-level interface for browser interaction and data capture.

- **Persistent Profile:** Uses a persistent Chromium context (`playwright_profiles/`) to maintain login sessions (cookies, localStorage).
- **Accessibility Map:** `get_state()` traverses the accessibility tree to create a numbered list of interactive elements (e.g., `[5] textbox: Project name`).
- **Visual Grounding:** Every action triggers a screenshot and metadata capture via `Scribe`, saved to `output/<timestamp>_<task_name>/`.

### MCP / Claude Integration
**File:** `src/server.py`

Softlight exposes its `BrowserTool` capabilities via the **Model Context Protocol (MCP)**, allowing external agents like **Claude Desktop** to act as Agent A.

**Exposed Tools:**
- `start_browser`
- `navigate_to`
- `get_screen_state`
- `perform_action`
- `ask_user_for_help`

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.12+**
- **OpenAI API Key** (for GPT-4o)

### Installation

You can set up the project using `uv` (recommended) or `pip`.

#### Using uv
```bash
uv sync
python -m playwright install chromium
```

#### Using pip
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### Configuration

Create a `.env` file in the project root and add your OpenAI API key:

```env
OPENAI_API_KEY=sk-...
```

---

## 💻 Usage

### Quick Start / Testing
To quickly test the system with interactive demos (Wikipedia, SauceDemo, Linear, or Custom), run the main entry point:

```bash
uv run main.py
```
This will launch a CLI menu where you can select a pre-configured demo task.

### Mode 1 – Local Multi-Agent (Planner A + Browser B)
This is the primary demo mode where the local planner directs the browser agent.

```bash
uv run python -m src.agent_planner "How do I create a new project in Linear and name it Softlight Demo? Capture each important step for me."
```

**Flow:**
1.  **Agent A** generates a plan (`plans/create_a_new_project...json`).
2.  **Agent B** executes the plan, recording screenshots to `output/`.

### Mode 2 – Direct Browser Agent (Agent B Only)
Bypass the planner to run a specific task directly.

```bash
uv run python -m src.agent
```
*Note: You may need to modify `__main__` in `src/agent.py` to specify your desired task.*

### Mode 3 – Claude as Agent A (MCP)
Integrate with Claude Desktop to use Claude as the high-level planner.

1.  **Configure Claude Desktop:** Add the following to your `claude_desktop_config.json`:

    ```json
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
    ```

2.  **Run in Claude:**
    > "Use the softlight-agent tools to open linear.app, create a new project named ‘Softlight Demo’, and capture each step."

---

## 📂 Dataset Layout

Every run generates a structured dataset containing plans and execution traces.

**Plan (Agent A):**
- `plans/<slug>.json`: Contains the original question and the concrete task prompt.

**Execution Trace (Agent B):**
- `output/<timestamp>_<task_name>/`:
  - `step_001.png`, `step_002.png`, ... (Screenshots of each state)
  - Metadata logs (captured by `Scribe`)

---

## 💡 Example Tasks

**Linear:**
> "How do I create a new project in Linear and name it ‘Softlight Demo’? Capture each important step for me."

**Wikipedia:**
> "How do I search for ‘Robotics’ on Wikipedia and open the main article? Capture each main screen."

**TodoMVC:**
> "How do I add a todo called ‘Softlight Demo’ in the React TodoMVC example and then mark it complete? Capture each UI state."

---

## ⚠️ Limitations & Future Work

- **Complex Modals:** Accessibility labels on complex modals (like Linear's "New project") can sometimes be ambiguous, leading to potential retry loops.
- **Token Limits:** The accessibility tree is truncated to fit within GPT-4o's context window. Smarter filtering could improve robustness.
- **Loop Detection:** Future improvements will include detecting repetitive actions to automatically switch strategies (e.g., fallback to keyboard typing).