#!/bin/bash
# SessionStart hook: prepares a Python virtual environment so Claude can run the
# tests in a Claude Code cloud session (the container starts with no packages).
#
# Safe to run every session:
#   - work that's already done is skipped (venv exists, requirements unchanged,
#     system library already present);
#   - it never fails the session: any problem is reported as a clear message and
#     the hook still exits 0, so the session starts and Claude can see what broke.

# The Python version for the venv. README says MediaPipe is tested on 3.11/3.12.
PYTHON_VERSION="3.12"

VENV_DIR=".venv"
REQUIREMENTS="requirements.txt"
# Hash of requirements.txt from the last successful install, kept inside the venv
# so deleting the venv also forgets it.
STAMP_FILE="$VENV_DIR/.requirements.sha256"
# MediaPipe's native library needs these graphics libraries to load. The cloud
# container doesn't ship them; without them the real-MediaPipe test is skipped.
# Each entry is "library file:apt package that provides it".
SYSTEM_LIBRARIES=(
  "libEGL.so.1:libegl1"
  "libGLESv2.so.2:libgles2"
)

# Only run in cloud sessions. On a local machine you manage your own venv
# (see README), and this bash script wouldn't run on Windows anyway.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

say() { echo "[session-start] $*"; }

# For optional steps: report the problem but keep going.
warn() {
  say "WARNING: $*"
}

# For essential steps: report the problem and stop (still exit 0, see above).
fail() {
  say "WARNING: $*"
  say "The session will continue, but tests may not run until this is fixed."
  say "Re-run by hand with: CLAUDE_CODE_REMOTE=true .claude/hooks/session-start.sh"
  exit 0
}

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || fail "could not cd into the project directory"

command -v uv >/dev/null 2>&1 || fail "uv is not installed, so the venv can't be created"
[ -f "$REQUIREMENTS" ] || fail "$REQUIREMENTS not found in $(pwd)"

# 1. Create the venv, or recreate it if it's broken or on a different Python.
current_version=""
if [ -x "$VENV_DIR/bin/python" ]; then
  current_version="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null)"
fi

if [ "$current_version" = "$PYTHON_VERSION" ]; then
  say "venv already uses Python $PYTHON_VERSION - skipping creation"
else
  if [ -n "$current_version" ]; then
    say "venv uses Python $current_version, not $PYTHON_VERSION - recreating it"
  else
    say "creating $VENV_DIR with Python $PYTHON_VERSION"
  fi
  # --clear replaces an existing (broken or wrong-version) venv instead of erroring.
  uv venv --clear --quiet --python "$PYTHON_VERSION" "$VENV_DIR" \
    || fail "could not create $VENV_DIR with Python $PYTHON_VERSION"
fi

# 2. Install the pinned packages, unless this exact requirements.txt is already in.
wanted_hash="$(sha256sum "$REQUIREMENTS" | cut -d' ' -f1)"
installed_hash="$(cat "$STAMP_FILE" 2>/dev/null)"

if [ "$wanted_hash" = "$installed_hash" ]; then
  say "packages from $REQUIREMENTS already installed - skipping install"
else
  say "installing packages from $REQUIREMENTS (this can take a minute)"
  uv pip install --quiet --python "$VENV_DIR/bin/python" -r "$REQUIREMENTS" \
    || fail "pip install from $REQUIREMENTS failed (see the error above)"
  echo "$wanted_hash" > "$STAMP_FILE"
fi

# 3. Install the system graphics libraries MediaPipe needs, unless they're already
#    there. Optional: if they can't be installed, everything else still works and
#    only the one real-MediaPipe test is skipped, so warn instead of stopping.
has_library() { ldconfig -p 2>/dev/null | grep -q "$1"; }

install_system_packages() {
  # Use sudo only when not already root (cloud sessions normally run as root).
  local sudo=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || return 1
    sudo="sudo -n"
  fi
  command -v apt-get >/dev/null 2>&1 || return 1
  # Try straight away; if the package lists are missing or stale, refresh them once.
  DEBIAN_FRONTEND=noninteractive $sudo apt-get install -y -qq "$@" >/dev/null 2>&1 && return 0
  $sudo apt-get update -qq >/dev/null 2>&1 \
    && DEBIAN_FRONTEND=noninteractive $sudo apt-get install -y -qq "$@" >/dev/null 2>&1
}

missing_packages=()
for entry in "${SYSTEM_LIBRARIES[@]}"; do
  library="${entry%%:*}"
  package="${entry##*:}"
  if has_library "$library"; then
    say "$library already installed - skipping $package"
  else
    missing_packages+=("$package")
  fi
done

if [ "${#missing_packages[@]}" -gt 0 ]; then
  say "installing ${missing_packages[*]} (graphics libraries for MediaPipe)"
  install_system_packages "${missing_packages[@]}"
  still_missing=()
  for entry in "${SYSTEM_LIBRARIES[@]}"; do
    has_library "${entry%%:*}" || still_missing+=("${entry##*:}")
  done
  if [ "${#still_missing[@]}" -eq 0 ]; then
    say "${missing_packages[*]} installed"
  else
    warn "could not install ${still_missing[*]} - the real-MediaPipe test in tests/test_tracker.py will be skipped; all other tests still run"
  fi
fi

# 4. Activate the venv for the rest of the session, so plain `python` and
#    `pytest` in Claude's shell use it.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$(pwd)/$VENV_DIR\""
    echo "export PATH=\"$(pwd)/$VENV_DIR/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi

say "ready: $("$VENV_DIR/bin/python" --version 2>&1) in $VENV_DIR - run tests with: .venv/bin/python -m pytest"
exit 0
