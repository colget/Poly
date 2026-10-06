"""PostToolUse hook: after Claude edits a file in poly/ or tests/, check the import
rules from CLAUDE.md and run the test suite.

Claude Code runs this after every Edit/MultiEdit/Write (see .claude/settings.json)
and passes the tool call as JSON on stdin. Exit codes:
  0 - nothing to do, or everything passed. Prints nothing.
  2 - an import rule is broken or a test failed. Claude Code feeds stderr back to
      Claude, so it sees the failure straight away and fixes it.
  1 - the hook itself can't run (e.g. no venv). Shown to the user, not blocking.

Stdlib only, so it runs with any Python 3 - the venv is only needed for pytest.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
WATCHED_DIRS = ("poly", "tests")

# Module -> the only file allowed to import it (CLAUDE.md "Conventions").
# Why: keeping MediaPipe and the real mouse in one file each is what lets the
# rest of the code be tested in a sandbox with no camera and no mouse.
ALLOWED_IMPORTERS = {
    "mediapipe": "poly/tracker.py",
    "pynput": "poly/cursor.py",
}

# How much pytest output to feed back on failure: enough for the traceback and
# summary, not so much that it floods Claude's context.
MAX_OUTPUT_LINES = 80


def edited_path(event: dict) -> Path | None:
    """Return the edited file relative to the project, or None if it's outside it."""
    file_path = event.get("tool_input", {}).get("file_path")
    if not file_path:
        return None
    try:
        return Path(file_path).resolve().relative_to(PROJECT_DIR.resolve())
    except ValueError:
        return None


def imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Top-level module names imported anywhere in the file, with line numbers.

    Walks the whole tree, so imports inside functions (like cursor.py's lazy
    pynput import) count too. Also catches importlib.import_module("x") and
    __import__("x") with a literal name.
    """
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name.split(".")[0], node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module.split(".")[0], node.lineno))
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            arg = node.args[0]
            if name in ("import_module", "__import__") and isinstance(arg, ast.Constant) \
                    and isinstance(arg.value, str):
                found.append((arg.value.split(".")[0], node.lineno))
    return found


def import_rule_violations() -> list[str]:
    """Check every .py file in poly/ and tests/ against ALLOWED_IMPORTERS."""
    problems = []
    for folder in WATCHED_DIRS:
        for path in sorted((PROJECT_DIR / folder).rglob("*.py")):
            rel = path.relative_to(PROJECT_DIR).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except SyntaxError as error:
                problems.append(f"{rel}:{error.lineno}: syntax error: {error.msg}")
                continue
            for module, line in imported_modules(tree):
                allowed = ALLOWED_IMPORTERS.get(module)
                if allowed and rel != allowed:
                    problems.append(f"{rel}:{line}: imports {module}, but only {allowed} may "
                                    f"(CLAUDE.md conventions)")
    return problems


def venv_python() -> Path | None:
    """The project's venv Python: .venv/bin (Linux/macOS) or .venv/Scripts (Windows)."""
    for candidate in (".venv/bin/python", ".venv/Scripts/python.exe"):
        path = PROJECT_DIR / candidate
        if path.exists():
            return path
    return None


def run_tests(python: Path) -> tuple[bool, str]:
    """Run the suite, stopping at the first failure. Returns (passed, output)."""
    result = subprocess.run(
        [str(python), "-m", "pytest", "-q", "-x"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main() -> int:
    event = json.load(sys.stdin)
    rel = edited_path(event)
    if rel is None or rel.parts[0] not in WATCHED_DIRS:
        return 0  # docs, README, config files etc.: nothing to check

    problems = import_rule_violations()
    if problems:
        print("Import rule broken:\n" + "\n".join(problems), file=sys.stderr)
        return 2

    python = venv_python()
    if python is None:
        print("check_edit hook: no .venv found, so tests were not run "
              "(in the cloud the SessionStart hook creates it)", file=sys.stderr)
        return 1

    passed, output = run_tests(python)
    if not passed:
        lines = output.rstrip().splitlines()
        if len(lines) > MAX_OUTPUT_LINES:
            lines = ["[... earlier output cut ...]"] + lines[-MAX_OUTPUT_LINES:]
        print(f"Tests failed after editing {rel.as_posix()}:\n" + "\n".join(lines),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
