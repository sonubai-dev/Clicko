"""Manual smoke test — performs a single non-destructive desktop action.

This script is NOT run by automated tests. It requires explicit human invocation.

What it does:
1. Prints the current screen dimensions
2. Asks for your explicit confirmation before proceeding
3. Moves the mouse to the center of the screen (a non-destructive action)
4. Takes a screenshot and reports its size
5. Moves the mouse back to its original position

Run with:
    .\.venv\Scripts\python.exe scripts\smoke_test.py
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        import pyautogui
    except ImportError:
        print("ERROR: pyautogui is not installed. Run:")
        print("  ..\\.venv\\Scripts\\python.exe -m pip install pyautogui")
        sys.exit(1)

    # Enable fail-safe
    pyautogui.FAILSAFE = True

    # Show screen info
    size = pyautogui.size()
    print(f"Screen dimensions: {size.width} x {size.height}")
    print()

    center_x = size.width // 2
    center_y = size.height // 2
    current_pos = pyautogui.position()
    print(f"Current mouse position: ({current_pos.x}, {current_pos.y})")
    print(f"Will move mouse to center: ({center_x}, {center_y})")
    print()

    # Explicit confirmation
    print("=" * 60)
    print("This will:")
    print(f"  1. Move the mouse to ({center_x}, {center_y})")
    print("  2. Take a screenshot (not saved to disk)")
    print(f"  3. Move the mouse back to ({current_pos.x}, {current_pos.y})")
    print()
    print("No clicks, typing, or other actions will be performed.")
    print("Move mouse to any screen corner to emergency-stop.")
    print("=" * 60)
    print()

    answer = input("Proceed? (yes/no): ").strip().lower()
    if answer != "yes":
        print("Cancelled.")
        sys.exit(0)

    print()
    print("Moving mouse to center...")
    pyautogui.moveTo(center_x, center_y, duration=1.0)
    print(f"Mouse is now at: {pyautogui.position()}")

    print("Taking screenshot...")
    import io
    screenshot = pyautogui.screenshot()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    png_size = len(buffer.getvalue())
    print(f"Screenshot captured: {png_size:,} bytes (not saved to disk)")

    print(f"Moving mouse back to ({current_pos.x}, {current_pos.y})...")
    pyautogui.moveTo(current_pos.x, current_pos.y, duration=1.0)
    print(f"Mouse is now at: {pyautogui.position()}")

    print()
    print("Smoke test completed successfully.")


if __name__ == "__main__":
    main()
