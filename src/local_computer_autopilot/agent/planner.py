"""Autonomous workflow planner with local LLM integration and rule-based fallback."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from local_computer_autopilot.agent.models import AgentMode, PlanStep, TaskPlan

logger = logging.getLogger("local_computer_autopilot.agent.planner")

OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "llama3"

ALLOWED_ACTIONS = frozenset({
    "computer_get_screen_info",
    "computer_screenshot",
    "computer_move_mouse",
    "computer_click",
    "computer_scroll",
    "computer_type_text",
    "computer_press_key",
    "computer_get_status",
    "visual_wait_for_change",
    "task_create",
    "task_record_step",
    "task_get_status",
    "task_list_history",
    "task_cancel",
    "desktop_list_windows",
    "desktop_focus_window",
    "desktop_get_window_bounds",
    "desktop_set_window_state",
    "browser_open",
    "browser_new_tab",
    "browser_list_tabs",
    "browser_switch_tab",
    "browser_close_tab",
    "browser_click",
    "browser_type",
    "browser_get_content",
    "browser_screenshot",
    "browser_close",
    "computer_get_monitors",
    "computer_clipboard_get",
    "computer_clipboard_set",
    "desktop_launch_app",
    "desktop_close_app",
    "visual_locate_element",
    "visual_click_element",
    "macro_create",
    "macro_list",
    "macro_execute",
    "macro_delete",
    "schedule_create",
    "schedule_list",
    "schedule_delete",
    "schedule_toggle",
    "audit_export_json",
    "audit_export_csv",
})


class WorkflowPlanner:
    """Plans multi-step execution sequences for high-level user goals."""

    def __init__(self, ollama_url: str = OLLAMA_API_URL, default_model: str = DEFAULT_OLLAMA_MODEL) -> None:
        self.ollama_url = ollama_url
        self.default_model = default_model

    def is_local_llm_available(self, timeout: float = 1.0) -> bool:
        """Check if local Ollama server is reachable."""
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                headers={"User-Agent": "Clicko-Autopilot"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def plan(self, goal: str, mode: AgentMode = AgentMode.AUTO) -> TaskPlan:
        """Generate an execution plan for the requested goal."""
        goal_clean = goal.strip()
        if not goal_clean:
            return TaskPlan(
                goal=goal,
                mode_used=AgentMode.STRUCTURED,
                steps=[],
                notes="Empty goal provided",
            )

        if mode in (AgentMode.LOCAL_LLM, AgentMode.AUTO):
            if self.is_local_llm_available():
                llm_plan = self._plan_with_local_llm(goal_clean)
                if llm_plan and llm_plan.steps:
                    return llm_plan
                logger.info("Local LLM planning did not yield valid steps; falling back to structured planner")
            elif mode == AgentMode.LOCAL_LLM:
                logger.warning("Local LLM requested but Ollama is not running on %s; using structured planner", self.ollama_url)

        return self._plan_with_rules(goal_clean)

    def _plan_with_local_llm(self, goal: str) -> TaskPlan | None:
        """Prompt local Ollama model to generate a structured JSON plan."""
        system_prompt = (
            "You are Clicko, a Windows Computer Autopilot. "
            "Output ONLY a raw JSON object with key 'steps' containing a list of objects with: "
            "'action_name' (e.g. browser_open, browser_type, browser_click, computer_click, desktop_focus_window, computer_screenshot), "
            "'parameters' (dict of args), 'description' (string), 'verify_visual' (boolean). "
            "Do NOT include markdown formatting or extra text."
        )
        payload = {
            "model": self.default_model,
            "prompt": f"{system_prompt}\n\nGoal: {goal}",
            "stream": False,
            "format": "json",
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.ollama_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                response_text = result.get("response", "")
                parsed = json.loads(response_text)
                steps_data = parsed.get("steps", [])

                plan_steps: list[PlanStep] = []
                for s in steps_data:
                    action_name = s.get("action_name", "")
                    if action_name not in ALLOWED_ACTIONS:
                        logger.warning("Local LLM planned unrecognized action '%s'; skipping step", action_name)
                        continue
                    plan_steps.append(
                        PlanStep(
                            step_number=len(plan_steps) + 1,
                            action_name=action_name,
                            parameters=s.get("parameters", {}),
                            description=s.get("description", f"Step {len(plan_steps) + 1}"),
                            verify_visual=bool(s.get("verify_visual", False)),
                            timeout_seconds=float(s.get("timeout_seconds", 10.0)),
                        )
                    )

                if plan_steps:
                    return TaskPlan(
                        goal=goal,
                        mode_used=AgentMode.LOCAL_LLM,
                        steps=plan_steps,
                        estimated_duration_seconds=len(plan_steps) * 2.5,
                        notes=f"Generated via local LLM ({self.default_model})",
                    )
        except Exception as e:
            logger.debug("Local LLM planning exception: %s", e)

        return None

    def _plan_with_rules(self, goal: str) -> TaskPlan:
        """Deterministic rule-based planner covering common automation workflows."""
        g = goal.lower()
        steps: list[PlanStep] = []

        # 1. Screenshot / Screen inspect workflows
        if any(w in g for w in ["screenshot", "screen info", "capture screen", "inspect screen"]):
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="computer_get_screen_info",
                    parameters={},
                    description="Retrieve primary monitor dimensions",
                    verify_visual=False,
                )
            )
            steps.append(
                PlanStep(
                    step_number=2,
                    action_name="computer_screenshot",
                    parameters={},
                    description="Capture full desktop screenshot",
                    verify_visual=False,
                )
            )

        # 2. Window / Desktop navigation workflows
        elif "focus" in g and ("window" in g or "app" in g):
            # Extract target name
            match = re.search(r"focus\s+(?:window\s+)?['\"]?([^'\"]+)['\"]?", g)
            target = match.group(1).strip() if match else "Notepad"
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="desktop_focus_window",
                    parameters={"query": target},
                    description=f"Bring window matching '{target}' to the foreground",
                    verify_visual=True,
                )
            )

        elif ("window" in g or "app" in g) and any(w in g for w in ["list", "find", "show", "running", "open"]):
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="desktop_list_windows",
                    parameters={},
                    description="Enumerate visible top-level Windows applications",
                    verify_visual=False,
                )
            )

        # 3. Browser workflows
        elif any(w in g for w in ["browser", "web", "search", "navigate", "open url", "http", "google"]):
            url = "https://www.bing.com"
            url_match = re.search(r"https?://[^\s]+", goal)
            if url_match:
                url = url_match.group(0)
            elif "google" in g:
                url = "https://www.google.com"
            elif "github" in g:
                url = "https://www.github.com"

            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="browser_open",
                    parameters={"url": url, "headless": False},
                    description=f"Launch browser and navigate to {url}",
                    verify_visual=True,
                )
            )

            # Check if search text was requested
            search_match = re.search(r"search (?:for )?['\"]?([^'\"]+)['\"]?", g)
            if search_match:
                query = search_match.group(1).strip()
                steps.append(
                    PlanStep(
                        step_number=2,
                        action_name="browser_type",
                        parameters={"selector": "input[type='search'], input[name='q']", "text": query},
                        description=f"Type search query into input field",
                        verify_visual=False,
                    )
                )
                steps.append(
                    PlanStep(
                        step_number=3,
                        action_name="computer_press_key",
                        parameters={"key": "enter"},
                        description="Press Enter to execute search",
                        verify_visual=True,
                    )
                )

            steps.append(
                PlanStep(
                    step_number=len(steps) + 1,
                    action_name="browser_screenshot",
                    parameters={},
                    description="Capture active browser page viewport",
                    verify_visual=False,
                )
            )

        # 4. Text typing / Notepad workflows
        elif any(w in g for w in ["type", "write", "enter text"]):
            text_match = re.search(r"(?:type|write)\s+['\"]?([^'\"]+)['\"]?", goal)
            text_to_type = text_match.group(1) if text_match else "Hello from Clicko Autopilot!"
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="computer_type_text",
                    parameters={"text": text_to_type},
                    description=f"Type requested text via keyboard",
                    verify_visual=True,
                )
            )

        # 5. Mouse actions
        elif "click" in g:
            coord_match = re.search(r"(\d+)\s*,\s*(\d+)", g)
            x, y = (int(coord_match.group(1)), int(coord_match.group(2))) if coord_match else (500, 500)
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="computer_click",
                    parameters={"x": x, "y": y, "click_type": "left"},
                    description=f"Click at screen coordinates ({x}, {y})",
                    verify_visual=True,
                )
            )

        # 6. Default general status check
        else:
            steps.append(
                PlanStep(
                    step_number=1,
                    action_name="computer_get_status",
                    parameters={},
                    description="Verify system health and safety controls",
                    verify_visual=False,
                )
            )
            steps.append(
                PlanStep(
                    step_number=2,
                    action_name="desktop_list_windows",
                    parameters={},
                    description="Inspect active desktop workspace state",
                    verify_visual=False,
                )
            )

        return TaskPlan(
            goal=goal,
            mode_used=AgentMode.STRUCTURED,
            steps=steps,
            estimated_duration_seconds=max(1.0, len(steps) * 1.5),
            notes="Generated via Clicko deterministic workflow rules",
        )
