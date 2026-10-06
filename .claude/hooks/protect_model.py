"""PreToolUse hook: stop Claude from editing or overwriting hand_landmarker.task.

CLAUDE.md: "Don't modify or re-download hand_landmarker.task." This has to be a
PreToolUse hook - it runs *before* the Edit/Write happens, so exiting with code 2
blocks the tool call. A PostToolUse hook would only find out after the file had
already been changed.

Exit codes:
  0 - not the model file: let the tool call go ahead.
  2 - the model file: block the call. Claude Code shows stderr to Claude as the
      reason, so it knows why and doesn't keep retrying.

Only covers Claude's file-editing tools (see the matcher in .claude/settings.json),
not shell commands.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
PROTECTED = PROJECT_DIR / "hand_landmarker.task"


def same_file(a: Path, b: Path) -> bool:
    """True if both paths name the same file (normcase: Windows paths ignore case)."""
    return os.path.normcase(a.resolve()) == os.path.normcase(b.resolve())


def main() -> int:
    tool_input = json.load(sys.stdin).get("tool_input", {})
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if target and same_file(Path(target), PROTECTED):
        print("Blocked: hand_landmarker.task is the MediaPipe model and must not be "
              "modified or replaced (CLAUDE.md conventions).", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
