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

        # Persistent browser profile so Linear stays logged in across runs
        here = os.path.dirname(os.path.abspath(__file__))
        self.user_data_dir = os.path.join(
            here,
            "..",
            "playwright_profiles",
            "linear_profile",
        )
        self.user_data_dir = os.path.normpath(self.user_data_dir)
        os.makedirs(self.user_data_dir, exist_ok=True)

        # Default startup session; will be overridden by agent_planner / server
        self.scribe.start_task("browser_tool", "startup_session", [])
        print(f"DEBUG: Scribe initialized at {self.scribe.current_task_dir}")
        print(f"DEBUG: Using persistent profile at {self.user_data_dir}")

    async def start(self):
        """
        Start a persistent Chromium context so that login sessions (cookies, localStorage)
        are reused across runs.
        """
        if self.playwright:
            return "Browser already running"

        self.playwright = await async_playwright().start()

        # Persistent context: reuses the same user_data_dir every time
        context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            slow_mo=1000,
            viewport={"width": 1280, "height": 720},
        )

        # Reuse existing page if present, otherwise open a new one
        if context.pages:
            self.page = context.pages[0]
        else:
            self.page = await context.new_page()

        return "Browser Started and Recording Initialized"

    async def navigate(self, url: str):
        if not self.page:
            await self.start()
        await self.page.goto(url)
        await self.page.wait_for_load_state("domcontentloaded")
        return f"Navigated to {url}"

    async def get_state(self):
        """
        Returns the current URL and a simplified accessibility-based element list.
        Elements are numbered [id] so the LLM can refer to them.
        """
        if not self.page:
            return {"url": "", "elements": []}

        snapshot = await self.page.accessibility.snapshot()
        self.element_map = {}
        simplified: list[str] = []

        def _traverse(node):
            role = node.get("role")
            name = node.get("name")
            if not role and not name:
                # Nothing useful here
                pass
            else:
                # We keep interactive or labelled elements to save tokens
                if role in ["button", "link", "textbox", "combobox", "menuitem"] or name:
                    el_id = len(self.element_map) + 1

                    try:
                        # Build a more descriptive label for the LLM
                        label_parts = []
                        if name:
                            label_parts.append(name)

                        value = node.get("value")
                        description = node.get("description")

                        if value:
                            label_parts.append(f"(value: {value})")
                        if description:
                            label_parts.append(f"- {description}")

                        label = " ".join(label_parts) or "<no-label>"

                        # Only attempt a locator if we have a role
                        if role:
                            if name:
                                loc = self.page.get_by_role(role, name=name).first
                            else:
                                loc = self.page.get_by_role(role).first

                            self.element_map[el_id] = loc
                            simplified.append(f"[{el_id}] {role}: {label}")
                    except Exception:
                        # If we can't resolve a locator, just skip this node
                        pass

            for child in node.get("children", []):
                _traverse(child)

        if snapshot:
            _traverse(snapshot)

        return {
            "url": self.page.url,
            "elements": simplified,
        }

    async def act(self, action_type: str, target_id: int, text: str = None):
        """
        Perform a click or type action on the element mapped by target_id.
        Also captures a screenshot + bounding box for each step via Scribe.
        """
        if target_id not in self.element_map:
            return "Error: Invalid ID"

        locator = self.element_map[target_id]

        try:
            # --- Visual grounding + screenshot ---
            if await locator.is_visible():
                box = await locator.bounding_box()
                if box:
                    self.step_index += 1
                    # Save screenshot into the current task directory
                    filename = f"step_{self.step_index:03d}.png"
                    screenshot_path = os.path.join(
                        self.scribe.current_task_dir,
                        filename,
                    )
                    os.makedirs(self.scribe.current_task_dir, exist_ok=True)
                    await self.page.screenshot(path=screenshot_path)

                    self.scribe.capture_step(
                        screenshot_path,
                        {"url": self.page.url},
                        {"type": action_type, "target": target_id, "text": text},
                        box,
                    )

            # --- Physical action ---
            if action_type == "click":
                await locator.click()

            elif action_type == "type":
                # More robust typing:
                # 1. Try fill() on the locator
                # 2. If that fails (e.g. container div), click to focus and type via keyboard
                typed_text = text or ""
                try:
                    await locator.fill(typed_text)
                except Exception:
                    await locator.click()
                    await self.page.keyboard.type(typed_text)

                # Try to submit with Enter; ignore failures
                try:
                    await self.page.keyboard.press("Enter")
                except Exception:
                    pass

            else:
                return f"Error: Unsupported action_type '{action_type}'"

            return "Action Success"

        except Exception as e:
            return f"Action Failed: {e}"
