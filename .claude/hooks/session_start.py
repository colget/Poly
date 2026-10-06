"""SessionStart launcher: runs session-start.sh in Claude Code cloud sessions only.

Why a Python launcher instead of calling the bash script directly: settings.json
runs every hook as `python <script>` so the same command works on Windows and
Linux. On Windows there may be no bash at all (or `bash` may be WSL's), so the
cloud-only check happens here, before bash is ever needed. On your own machine you
manage your own venv (see README), so this does nothing there.
"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("session-start.sh")


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true":
        return 0
    # The bash script's output goes straight through to Claude Code. It always
    # exits 0 (see the script), so a problem never stops the session starting.
    return subprocess.run(["bash", str(SCRIPT)]).returncode


if __name__ == "__main__":
    sys.exit(main())
