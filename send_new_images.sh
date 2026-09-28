#!/usr/bin/env bash
# send_new_images.sh
# Bash wrapper to call the Python script that sends new images from the monitored folder
# Usage: place sensitive environment variables into send_env.sh (next to this script) and make sure
# that file is not committed. See send_env.sh.template or README for details.

set -euo pipefail

# Resolve the real directory of this script, even when invoked via a symlink.
# dirname of ${BASH_SOURCE[0]} alone returns the symlink's directory, which
# breaks lookups for venv/, send_env.sh and send_new_images.py.
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  # If the symlink target was relative, resolve it relative to the symlink dir
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
PY="python3"

# If a local virtualenv exists at ./venv, activate it so the script uses the venv's Python and packages.
if [ -f "${SCRIPT_DIR}/venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/venv/bin/activate"
  # Set PY to the venv python executable for direct invocation
  if [ -x "${SCRIPT_DIR}/venv/bin/python" ]; then
    PY="${SCRIPT_DIR}/venv/bin/python"
  fi
fi

# If a local send_env.sh exists next to this script, source it. This file should
# contain sensitive credentials (EMAIL_USER, EMAIL_PASS) and must NOT be committed.
if [ -f "${SCRIPT_DIR}/send_env.sh" ]; then
  # shellcheck source=/dev/null
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/send_env.sh"
fi

"$PY" "${SCRIPT_DIR}/send_new_images.py" "$@"
