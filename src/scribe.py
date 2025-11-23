import os
import json
import time

class Scribe:
    def __init__(self):
        self.output_dir = "output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.current_task_dir = None
        self.logs = []

    def start_task(self, app_name, task_name, plan):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        safe_task_name = "".join(x for x in task_name if x.isalnum() or x in " -_").strip().replace(" ", "_")
        self.current_task_dir = os.path.join(self.output_dir, f"{timestamp}_{safe_task_name}")
        os.makedirs(self.current_task_dir, exist_ok=True)
        
        self.log(f"Starting task: {task_name}")
        self.log(f"Plan: {plan}")
        
        # Save metadata
        with open(os.path.join(self.current_task_dir, "metadata.json"), "w") as f:
            json.dump({
                "app": app_name,
                "task": task_name,
                "plan": plan,
                "timestamp": timestamp
            }, f, indent=2)

    def log(self, message):
        print(f"[Scribe]: {message}")
        self.logs.append(message)

    def capture_step(self, screenshot_path, state, action, target_bbox):
        if not self.current_task_dir:
            self.log("Warning: No task started, cannot capture step.")
            return

        step_id = len([f for f in os.listdir(self.current_task_dir) if f.endswith(".json")]) - 1 # exclude metadata
        step_id += 1
        
        # Move/Copy screenshot
        dest_screenshot = os.path.join(self.current_task_dir, f"step_{step_id}.png")
        try:
            # If screenshot_path is a temp file, we might want to move or copy it
            # For now, assuming the browser saved it to 'temp.png' or similar relative path
            import shutil
            shutil.copy(screenshot_path, dest_screenshot)
        except Exception as e:
            self.log(f"Failed to save screenshot: {e}")

        # Save step data
        step_data = {
            "step_id": step_id,
            "state": state, # This might be large
            "action": action,
            "target_bbox": target_bbox
        }
        
        with open(os.path.join(self.current_task_dir, f"step_{step_id}.json"), "w") as f:
            json.dump(step_data, f, indent=2)
            
        self.log(f"Captured step {step_id}")
