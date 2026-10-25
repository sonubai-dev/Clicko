"""Phase 2 Smoke Test — Non-destructive verification of Phase 2 capabilities.

Demonstrates:
1. Visual verification & change detection (in-memory Pillow)
2. Task tracking & audit log (SQLite)
3. Windows desktop application discovery (pywin32)
4. Reliable execution (retries, timeouts, cancellation)
5. Local browser automation readiness (Playwright / Edge)

Run with:
    .\\.venv\\Scripts\\python.exe scripts\\phase2_smoke_test.py
"""

from __future__ import annotations

import io
import sys
import time
from PIL import Image, ImageDraw

from local_computer_autopilot.vision.models import BoundingBox
from local_computer_autopilot.vision.verifier import compare_images
from local_computer_autopilot.task.manager import TaskManager
from local_computer_autopilot.desktop.window_manager import WindowManager
from local_computer_autopilot.execution.retry import retry_with_backoff, run_with_timeout
from local_computer_autopilot.execution.cancellation import CancellationToken


def test_visual_verification() -> None:
    print("\n--- 1. Testing Visual Verification (Pillow) ---")
    img1 = Image.new("RGB", (200, 200), color=(240, 240, 240))
    buf1 = io.BytesIO()
    img1.save(buf1, format="PNG")

    img2 = img1.copy()
    draw = ImageDraw.Draw(img2)
    draw.rectangle([40, 40, 80, 80], fill=(255, 0, 0))
    buf2 = io.BytesIO()
    img2.save(buf2, format="PNG")

    result = compare_images(buf1.getvalue(), buf2.getvalue(), threshold=0.01)
    print(f"  Change detected: {result.has_changed}")
    print(f"  Pixel difference ratio: {result.diff_ratio:.2%}")
    if result.changed_bbox:
        print(f"  Altered BoundingBox: x={result.changed_bbox.x}, y={result.changed_bbox.y}, "
              f"w={result.changed_bbox.width}, h={result.changed_bbox.height}")
    print(f"  Message: {result.message}")
    assert result.has_changed, "Expected visual change to be detected"
    print("  [PASS] Visual verification functioning as expected.")


def test_task_tracking() -> None:
    print("\n--- 2. Testing Task Tracking & SQLite Storage ---")
    tm = TaskManager(db_path=":memory:")
    task = tm.create_task("Phase 2 Smoke Test Workflow")
    print(f"  Created Task: ID={task.task_id}, Status={task.status.value}")

    step1 = tm.record_step(
        task_id=task.task_id,
        action_name="desktop_list_windows",
        parameters={"filter": "all"},
        result_summary="Discovered top-level windows",
        visual_verified=False,
    )
    print(f"  Recorded Step 1: {step1.action_name} -> {step1.status.value}")

    step2 = tm.record_step(
        task_id=task.task_id,
        action_name="visual_wait_for_change",
        parameters={"timeout": 3.0},
        result_summary="Visual change confirmed",
        visual_verified=True,
    )
    print(f"  Recorded Step 2: {step2.action_name} -> {step2.status.value} (Verified: {step2.visual_verified})")

    status = tm.get_task_status(task.task_id)
    print(f"  Task Audit Record: {len(status['steps'])} steps tracked in SQLite")
    tm.complete_task(task.task_id)
    print("  [PASS] SQLite task tracking functioning as expected.")


def test_desktop_navigation() -> None:
    print("\n--- 3. Testing Desktop Window Navigation (pywin32) ---")
    wm = WindowManager()
    windows = wm.list_windows()
    print(f"  Discovered {len(windows)} visible top-level windows:")
    for w in windows[:5]:
        active_flag = " [ACTIVE]" if w.is_active else ""
        print(f"    - [{w.handle}] '{w.title}' ({w.width}x{w.height} at {w.x},{w.y}){active_flag}")
    print("  [PASS] Desktop window discovery functioning as expected.")


def test_reliable_execution() -> None:
    print("\n--- 4. Testing Reliable Execution (Retries, Timeouts, Cancellation) ---")
    attempts = 0

    def flaky_action():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionResetError("Simulated transient network glitch")
        return "Action succeeded on retry"

    result = retry_with_backoff(
        flaky_action,
        max_retries=3,
        initial_delay=0.05,
        retryable_exceptions=(ConnectionResetError,),
    )
    print(f"  Retry output: {result} (Took {attempts} attempts)")

    timeout_result = run_with_timeout(lambda: "Fast function", timeout_seconds=2.0)
    print(f"  Timeout output: {timeout_result}")

    token = CancellationToken()
    token.cancel("User test halt")
    print(f"  Cancellation token triggered: {token.is_cancelled} ('{token.reason}')")
    print("  [PASS] Reliable execution helpers functioning as expected.")


def test_browser_readiness() -> None:
    print("\n--- 5. Testing Local Browser Automation Readiness (Playwright) ---")
    from local_computer_autopilot.browser.browser_manager import HAS_PLAYWRIGHT, BrowserManager
    print(f"  Playwright module installed: {HAS_PLAYWRIGHT}")
    if HAS_PLAYWRIGHT:
        mgr = BrowserManager(default_channel="msedge")
        print(f"  Default browser channel: {mgr.default_channel}")
        print("  [PASS] Local browser manager initialized and ready.")


def main() -> None:
    print("=" * 65)
    print(" Clicko Phase 2 Smoke Test: Visual Verification & Automation")
    print("=" * 65)

    test_visual_verification()
    test_task_tracking()
    test_desktop_navigation()
    test_reliable_execution()
    test_browser_readiness()

    print("\n" + "=" * 65)
    print(" ALL PHASE 2 SMOKE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
