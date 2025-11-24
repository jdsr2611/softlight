import asyncio
import json
from playwright.async_api import async_playwright
from src.scribe import Scribe

class BrowserTool:
    def __init__(self):
        self.playwright = None
        self.page = None
        self.scribe = Scribe()
        self.element_map = {} 
        
        # FORCE START: Create a default recording folder immediately
        self.scribe.start_task("claude_desktop", "auto_session", [])
        print(f"DEBUG: Scribe initialized at {self.scribe.current_task_dir}")
    async def start(self):
            if self.playwright: return "Browser already running"
            
            # --- NEW: Auto-Initialize the Scribe Folder ---
            # This ensures every time Claude opens a browser, a folder is ready.
            self.scribe.start_task("claude_desktop", "interactive_session", [])
            print(f"DEBUG: Scribe recording to {self.scribe.current_task_dir}")
            # ---------------------------------------------

            self.playwright = await async_playwright().start()
            # Headless=False so you can watch it work!
            browser = await self.playwright.chromium.launch(headless=False, slow_mo=1000)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            self.page = await context.new_page()
            return "Browser Started and Recording Initialized"

    async def navigate(self, url: str):
        if not self.page: await self.start()
        await self.page.goto(url)
        await self.page.wait_for_load_state("domcontentloaded")
        return f"Navigated to {url}"

    async def get_state(self):
        """Returns the URL and the Simplified Accessibility Tree"""
        if not self.page: return {"url": "", "elements": []}
        
        snapshot = await self.page.accessibility.snapshot()
        self.element_map = {} # Reset map
        
        simplified = []
        
        def _traverse(node):
            # Only keep interactive elements to save tokens
            if node.get('role') in ['button', 'link', 'textbox', 'combobox', 'menuitem'] or node.get('name'):
                el_id = len(self.element_map) + 1
                # Store the locator strategy
                try:
                    if node.get('name'):
                        loc = self.page.get_by_role(node['role'], name=node['name']).first
                    else:
                        loc = self.page.get_by_role(node['role']).first
                    
                    self.element_map[el_id] = loc
                    simplified.append(f"[{el_id}] {node.get('role')}: {node.get('name', '')}")
                except:
                    pass
            
            for child in node.get('children', []):
                _traverse(child)

        if snapshot: _traverse(snapshot)
        
        return {
            "url": self.page.url,
            "elements": simplified
        }
    async def act(self, action_type: str, target_id: int, text: str = None):
            if target_id not in self.element_map:
                return "Error: Invalid ID"
                
            locator = self.element_map[target_id]
            
            try:
                # Visual Grounding
                if await locator.is_visible():
                    box = await locator.bounding_box()
                    if box:
                        await self.page.screenshot(path="temp.png")
                        self.scribe.capture_step(
                            "temp.png", 
                            {"url": self.page.url}, 
                            {"type": action_type, "target": target_id}, 
                            box
                        )
                
                # Physical Action
                if action_type == "click":
                    await locator.click()
                elif action_type == "type":
                    await locator.fill(text)
                    # PRO TRICK: Press Enter after typing to submit forms automatically
                    await locator.press("Enter") 
                    
                return "Action Success"
            except Exception as e:
                return f"Action Failed: {e}"