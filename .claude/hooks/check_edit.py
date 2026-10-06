"""PostToolUse hook: after Claude edits a file in poly/ or tests/, check the import
rules from CLAUDE.md and run the test suite.

Claude Code runs this after every Edit/MultiEdit/Write (see .claude/settings.json)
and passes the tool call as JSON on stdin. Exit codes:
  0 - nothing to do, or everything passed. Prints nothing.
  2 - an import rule is broken or a test failed. Claude Code feeds stderr back to
      Claude, so it sees the failure straight away and fixes it.
  1 - no Python with pytest was found. Shown to the user, not blocking.

Works on Windows and Linux. Stdlib only, so any Python 3 can run the hook itself;
pytest only needs to be in the Python that runs the tests (see find_test_python).
"""

import ast
import importlib.util
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

# Where to look for a venv, in order: ".venv" is what the cloud SessionStart hook
# makes, "venv" is what the README tells you to make on Windows.
VENV_NAMES = (".venv", "venv")
# A venv's Python lives in bin/ on Linux/macOS and in Scripts\ on Windows.
VENV_PYTHONS = ("bin/python", "Scripts/python.exe")


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


def venv_has_pytest(venv: Path) -> bool:
    """True if pytest is installed in this venv. Checks the folder instead of starting
    the venv's Python, so the hook stays fast. site-packages is in lib/pythonX.Y on
    Linux/macOS and in Lib on Windows."""
    return any(venv.glob("lib/python*/site-packages/pytest")) \
        or (venv / "Lib" / "site-packages" / "pytest").is_dir()


def find_test_python(project_dir: Path) -> Path | None:
    """The Python to run the tests with: the first venv in VENV_NAMES that has pytest,
    else the Python running this hook if it has pytest, else None.

    The fallback is for running Poly with a main Python install and no venv. A venv
    without pytest is skipped rather than used, because running it would only fail
    with "No module named pytest" on every edit.
    """
    for venv_name in VENV_NAMES:
        venv = project_dir / venv_name
        for python in VENV_PYTHONS:
            if (venv / python).exists() and venv_has_pytest(venv):
                return venv / python
    if importlib.util.find_spec("pytest") is not None:
        return Path(sys.executable)
    return None


def run_tests(python: Path) -> tuple[bool, str]:
    """Run the suite, stopping at the first failure. Returns (passed, output)."""
    # Ask pytest for UTF-8 and decode it as UTF-8: on Windows, piped output would
    # otherwise use the old code page and choke on characters like the "±" in
    # pytest.approx failures.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [str(python), "-m", "pytest", "-q", "-x"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main() -> int:
    # Claude Code talks to hooks in UTF-8. Python on Windows would use the old code
    # page for pipes, so set both ends explicitly.
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    rel = edited_path(event)
    if rel is None or not rel.parts or rel.parts[0] not in WATCHED_DIRS:
        return 0  # docs, README, config files etc.: nothing to check

    problems = import_rule_violations()
    if problems:
        print("Import rule broken:\n" + "\n".join(problems), file=sys.stderr)
        return 2

    python = find_test_python(PROJECT_DIR)
    if python is None:
        print("check_edit hook: tests were not run - no Python with pytest found "
              f"(looked in {' and '.join(VENV_NAMES)}, then {sys.executable}). "
              "Install pytest, e.g. with: pip install -r requirements.txt",
              file=sys.stderr)
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
