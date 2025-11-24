import sys
import asyncio

# 1. Print immediately to prove Python started
print("DEBUG: Python script has started!", file=sys.stderr)

try:
    from mcp.server.fastmcp import FastMCP
    print("DEBUG: Imported FastMCP successfully", file=sys.stderr)
    
    from src.tools import BrowserTool
    print("DEBUG: Imported BrowserTool successfully", file=sys.stderr)

except ImportError as e:
    print(f"CRITICAL ERROR: Missing library -> {e}", file=sys.stderr)
    sys.exit(1)

# Initialize the Server
mcp = FastMCP("Softlight Agent")
print("DEBUG: FastMCP initialized", file=sys.stderr)

browser_tool = BrowserTool()

@mcp.tool()
async def start_browser() -> str:
    """Opens the chrome window. Call this first."""
    print("DEBUG: Tool 'start_browser' called", file=sys.stderr)
    return await browser_tool.start()

@mcp.tool()
async def navigate_to(url: str) -> str:
    """Navigates the browser to a URL."""
    print(f"DEBUG: Tool 'navigate_to' called with {url}", file=sys.stderr)
    return await browser_tool.navigate(url)

@mcp.tool()
async def get_screen_state() -> str:
    """Returns the current state of the screen."""
    state = await browser_tool.get_state()
    return f"URL: {state['url']}\nElements:\n" + "\n".join(state['elements'])

@mcp.tool()
async def perform_action(action: str, target_id: int, text: str = None) -> str:
    """Interacts with the page."""
    print(f"DEBUG: Action {action} on {target_id}", file=sys.stderr)
    return await browser_tool.act(action, target_id, text)

@mcp.tool()
async def ask_user_for_help(question: str) -> str:
    return f"REQUEST_FROM_AGENT: {question}"

if __name__ == "__main__":
    print("DEBUG: Starting Server Run Loop...", file=sys.stderr)
    try:
        mcp.run()
    except Exception as e:
        print(f"CRITICAL ERROR in mcp.run(): {e}", file=sys.stderr)