import sys
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from .tools import BrowserTool  # relative import from the src package


# Initialize MCP server
mcp = FastMCP("Softlight Agent")
print("DEBUG: FastMCP initialized", file=sys.stderr)

browser_tool = BrowserTool()
current_task_dir: str | None = None


def _init_scribe_session(task_name: str | None = None) -> str:
    global current_task_dir

    if not task_name:
        task_name = datetime.now().strftime("claude_session_%Y%m%d_%H%M%S")

    browser_tool.scribe.start_task(
        "claude_agent",
        task_name,
        [],
    )

    current_task_dir = getattr(browser_tool.scribe, "current_task_dir", None)
    abs_dir = os.path.abspath(current_task_dir)
    print(f"DEBUG: Scribe task for Claude at: {current_task_dir}", file=sys.stderr)
    print(f"DEBUG: Absolute Scribe dir: {abs_dir}", file=sys.stderr)
    return str(current_task_dir)



@mcp.tool()
async def start_browser(task_name: str | None = None) -> str:
    """
    Opens the Chromium window and initializes a capture session for Claude.

    Optional:
      task_name: Name for this capture run (folder under Scribe output root).
    """
    print("DEBUG: Tool 'start_browser' called", file=sys.stderr)
    task_dir = _init_scribe_session(task_name)
    await browser_tool.start()
    return f"Browser started. Capturing screenshots in: {task_dir}"


@mcp.tool()
async def navigate_to(url: str) -> str:
    """Navigates the browser to a URL."""
    print(f"DEBUG: Tool 'navigate_to' called with {url}", file=sys.stderr)
    return await browser_tool.navigate(url)


@mcp.tool()
async def get_screen_state() -> str:
    """
    Returns the current state of the screen: URL + numbered element list.
    Screenshots for each action are handled in BrowserTool.act via Scribe.
    """
    state = await browser_tool.get_state()
    return f"URL: {state['url']}\nElements:\n" + "\n".join(state["elements"])


@mcp.tool()
async def perform_action(action: str, target_id: int, text: str | None = None) -> str:
    """Interacts with the page (click/type) and triggers screenshot capture."""
    print(f"DEBUG: Action {action} on {target_id}", file=sys.stderr)
    return await browser_tool.act(action, target_id, text)


@mcp.tool()
async def ask_user_for_help(question: str) -> str:
    """Used by the LLM to surface questions back to the human."""
    return f"REQUEST_FROM_AGENT: {question}"


if __name__ == "__main__":
    print("DEBUG: Starting Server Run Loop...", file=sys.stderr)
    try:
        mcp.run()
    except Exception as e:
        print(f"CRITICAL ERROR in mcp.run(): {e}", file=sys.stderr)
