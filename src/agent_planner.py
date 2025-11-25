import os
import re
import sys
import json
import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Agent B (browser executor) - note the relative import
from .agent import run_autonomous_agent


# 1. Load API key
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)


def _slugify(text: str) -> str:
    """
    Turn a free-form question into a filesystem-friendly task name.
    """
    text = text.lower().strip()
    words = text.split()
    text = " ".join(words[:8])  # first ~8 words
    slug = re.sub(r"[^a-z0-9]+", "_", text)
    slug = slug.strip("_")
    return slug or "task"


def _get_repo_root() -> str:
    """
    Compute repo root assuming this file is in src/.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    return repo_root


async def planner_agent(user_question: str):
    """
    Planner Agent (Agent A).

    - Takes a high-level user question like:
        "How do I create a project in Linear?"
    - Uses GPT-4o to rewrite it into a concrete browser task prompt for Agent B.
    - Saves that instruction to a file for traceability / dataset.
    - Calls Agent B (run_autonomous_agent) with that refined prompt.
    """
    print("\n🧩 Agent A (Planner) received question:")
    print(f"   {user_question}")

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    system = SystemMessage(
        content="""
You are Planner Agent A.

Your job is to convert a vague user question into a very explicit,
actionable task description for a browser agent (Agent B).

Agent B can ONLY:
- open URLs (navigate),
- click elements by ID,
- type into fields, and
- press Enter.

Rewrite the question into a single, clear TASK that Agent B can execute
step-by-step in a web browser. Mention the target website explicitly,
and what should be achieved on the page.

Do NOT add any JSON or bullet lists. Just output the final task sentence(s).
        """.strip()
    )

    human = HumanMessage(content=user_question)

    resp = await llm.ainvoke([system, human])
    task_prompt = resp.content.strip()

    print("\n🧩 Planner Agent A produced concrete task for Agent B:")
    print(f"   {task_prompt}\n")

    # ---- Save Agent A's instructions to a file ----
    task_slug = _slugify(user_question)
    repo_root = _get_repo_root()
    plans_dir = os.path.join(repo_root, "plans")
    os.makedirs(plans_dir, exist_ok=True)

    plan_path = os.path.join(plans_dir, f"{task_slug}.json")

    plan_payload = {
        "user_question": user_question,
        "agent_b_task_prompt": task_prompt,
    }

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_payload, f, indent=2, ensure_ascii=False)

    print(f"📝 Agent A instructions saved to: {plan_path}")

    # ---- Delegate to Agent B (browser agent) ----
    await run_autonomous_agent(task_prompt, task_slug)


async def _amain():
    # CLI usage:
    #   uv run python -m src.agent_planner "How do I create a project in Linear?"
    if len(sys.argv) > 1:
        user_question = " ".join(sys.argv[1:])
    else:
        user_question = input("Enter a high-level question for Agent A:\n> ").strip()

    if not user_question:
        print("❌ No question provided. Exiting.")
        return

    await planner_agent(user_question)


if __name__ == "__main__":
    asyncio.run(_amain())
