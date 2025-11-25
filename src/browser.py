import asyncio
from playwright.async_api import async_playwright

import os
from playwright.async_api import async_playwright
from src.scribe import Scribe

class BrowserTool:
    def __init__(self):
        self.playwright = None
        self.page = None
        self.scribe = Scribe()
        self.element_map = {}
        self.step_index = 0

        # Folder where Chromium will store cookies, localStorage, etc.
        self.user_data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "playwright_profiles",
            "linear_profile",
        )

        self.scribe.start_task("browser_tool", "startup_session", [])
        print(f"DEBUG: Scribe initialized at {self.scribe.current_task_dir}")

    async def start(self):
        if self.playwright:
            return "Browser already running"

        self.playwright = await async_playwright().start()

        # 🔑 Persistent context: reuses the same profile folder every run
        context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            slow_mo=1000,
            viewport={"width": 1280, "height": 720},
        )

        self.page = await context.new_page()
        return "Browser Started and Recording Initialized"


    async def get_current_state(self):
        if not self.page:
            return {"url": "", "interactive_elements": []}
        
        url = self.page.url
        
        # Simple accessibility snapshot for now
        snapshot = await self.page.accessibility.snapshot()
        
        # Flatten and map elements to IDs for the LLM
        self.element_map = {}
        elements = []
        
        def traverse(node, index_counter):
            role = node.get("role")
            name = node.get("name")
            
            # Filter for interesting elements
            if role in ["button", "link", "textbox", "combobox", "menuitem", "checkbox", "radio"] or (role == "text" and name):
                idx = index_counter[0]
                self.element_map[idx] = node # In a real app we'd store a locator or handle
                elements.append({
                    "id": idx,
                    "role": role,
                    "name": name,
                    # "value": node.get("value") 
                })
                index_counter[0] += 1
            
            for child in node.get("children", []):
                traverse(child, index_counter)

        traverse(snapshot, [0])
        
        return {
            "url": url,
            "interactive_elements": elements
        }

    async def highlight_element(self, target_id):
        # In a real implementation, we would use the accessibility node to find the element.
        # For this simplified version, we'll try to find it by role/name from the stored map.
        # This is tricky without direct handle mapping from accessibility snapshot.
        # Let's try to reconstruct a locator.
        
        node = self.element_map.get(target_id)
        if not node:
            print(f"Element {target_id} not found in map.")
            return None

        role = node.get("role")
        name = node.get("name")
        
        try:
            if role and name:
                locator = self.page.get_by_role(role, name=name).first
            elif role:
                locator = self.page.get_by_role(role).first # Very risky
            else:
                return None

            if await locator.count() > 0:
                box = await locator.bounding_box()
                # Draw a red box
                await self.page.evaluate("""
                    (box) => {
                        const div = document.createElement('div');
                        div.id = 'softlight-highlight';
                        div.style.position = 'absolute';
                        div.style.left = box.x + 'px';
                        div.style.top = box.y + 'px';
                        div.style.width = box.width + 'px';
                        div.style.height = box.height + 'px';
                        div.style.border = '2px solid red';
                        div.style.zIndex = '10000';
                        document.body.appendChild(div);
                    }
                """, box)
                return box
        except Exception as e:
            print(f"Failed to highlight: {e}")
        
        return None

    async def clear_highlights(self):
        if self.page:
            await self.page.evaluate("""
                () => {
                    const el = document.getElementById('softlight-highlight');
                    if (el) el.remove();
                }
            """)

    async def perform_action(self, action, target_id, text_content=None):
        node = self.element_map.get(target_id)
        if not node:
            print(f"Element {target_id} not found for action.")
            return

        role = node.get("role")
        name = node.get("name")
        
        try:
            locator = self.page.get_by_role(role, name=name).first
            
            if action == "click":
                await locator.click()
            elif action == "type" and text_content:
                await locator.fill(text_content)
            elif action == "wait":
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"Action failed: {e}")

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
