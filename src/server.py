import asyncio
import json
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

# Import our helper logic (we will keep Scribe as a helper class)
from src.scribe import Scribe

# Initialize the MCP Server
mcp = FastMCP("Softlight Data Collector")

# Global state for the server
class ServerState:
    playwright = None
    browser = None
    page = None
    scribe = None

state = ServerState()

@mcp.resource("accessibility_tree://current")
async def get_accessibility_tree() -> str:
    """Returns the simplified accessibility tree of the current page."""
    if not state.page:
        return "Browser not started."
    
    snapshot = await state.page.accessibility.snapshot()
    
    # Simplified tree parser (same logic as before)
    def parse(node):
        interesting = {'button', 'link', 'textbox', 'combobox', 'menuitem'}
        if node.get('role') in interesting or node.get('name'):
             return f"[{node.get('role')}]: {node.get('name')} (ID: {node.get('role')}_{node.get('name')})"
        return None

    # (In production, we'd do full recursive parsing here)
    return json.dumps(snapshot, indent=2)

@mcp.tool()
async def open_browser(task_name: str, app_name: str) -> str:
    """
    Starts the browser session and initializes the Scribe dataset recorder.
    """
    state.playwright = await async_playwright().start()
    # Use persistent context for login retention
    state.browser = await state.playwright.chromium.launch_persistent_context(
        user_data_dir="./browser_data",
        headless=False, # Headless=False so you can see it working
        viewport={"width": 1280, "height": 720}
    )
    state.page = state.browser.pages[0]
    
    # Init Scribe
    state.scribe = Scribe()
    state.scribe.start_task(app_name, task_name, [])
    
    return "Browser started and Scribe recording initialized."

@mcp.tool()
async def navigate(url: str) -> str:
    """Navigates to a URL."""
    if not state.page: return "Error: Browser not open."
    await state.page.goto(url)
    return f"Navigated to {url}"

@mcp.tool()
async def click_element(selector_role: str, selector_name: str) -> str:
    """
    Clicks an element and captures the dataset entry (Screenshot + BBox).
    """
    if not state.page: return "Error: Browser not open."

    # 1. Locate
    # Note: In a real implementation, we would use the unique IDs we generated
    # For this demo, we use the role/name from the LLM
    locator = state.page.get_by_role(selector_role, name=selector_name).first
    
    if await locator.count() == 0:
        return "Error: Element not found."

    # 2. Visual Grounding (Get Box)
    box = await locator.bounding_box()
    
    # 3. Capture State (The "Before" Shot)
    screenshot_path = "temp_screenshot.png"
    await state.page.screenshot(path=screenshot_path)
    
    # 4. Scribe It!
    acc_tree = await state.page.accessibility.snapshot()
    state.scribe.capture_step(
        screenshot_path, 
        state={"url": state.page.url, "interactive_elements": acc_tree}, 
        action={"type": "click", "description": f"{selector_role} {selector_name}"}, 
        target_bbox=box
    )

    # 5. Act
    await locator.click()
    return "Clicked and captured."

@mcp.tool()
async def type_text(selector_role: str, selector_name: str, text: str) -> str:
    """Types text into a field and captures the state."""
    if not state.page: return "Error: Browser not open."
    
    locator = state.page.get_by_role(selector_role, name=selector_name).first
    box = await locator.bounding_box()
    
    # Scribe
    await state.page.screenshot(path="temp_screenshot.png")
    acc_tree = await state.page.accessibility.snapshot()
    state.scribe.capture_step(
        "temp_screenshot.png", 
        {"url": state.page.url, "interactive_elements": acc_tree}, 
        {"type": "type", "description": f"Typed '{text}' into {selector_name}"}, 
        box
    )

    await locator.fill(text)
    return "Typed text and captured."

if __name__ == "__main__":
    # This allows you to run `python src/server.py` and connect to it
    mcp.run()