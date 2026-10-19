#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-hybrid}"
JOBS="${JOBS:-1}"
PYTHON_BIN="${PYTHON:-python}"

case "$CONFIG" in
  hybrid|debug) ;;
  *)
    echo "Usage: $0 [hybrid|debug]" >&2
    exit 2
    ;;
esac

if ! command -v make >/dev/null 2>&1; then
  echo "ERROR: GNU make is required." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: BigWorld's Linux build requires Python 2.7 as 'python'." >&2
  echo "       Set PYTHON=/path/to/python2.7 or use the supported CentOS 7 build environment." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[0] == 2 else 1)'; then
  echo "ERROR: $PYTHON_BIN is not Python 2.x. The checked-in platform detector uses Python 2 syntax." >&2
  echo "       Build in the repository's supported CentOS 7 environment." >&2
  exit 1
fi

if [[ ! -r /etc/redhat-release ]] || ! grep -Eq 'CentOS.*release 7|Red Hat.*release 7' /etc/redhat-release; then
  echo "ERROR: this build preset targets CentOS/RHEL 7 (el7)." >&2
  echo "       Current host: $(cat /etc/os-release 2>/dev/null | grep '^PRETTY_NAME=' | cut -d= -f2- || uname -s)" >&2
  echo "       Use a CentOS 7 VM/container with Python 2.7 and the dependencies in NOTE." >&2
  exit 1
fi

if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: JOBS must be a positive integer." >&2
  exit 2
fi

echo "Building BigWorld server components: config=$CONFIG jobs=$JOBS"
make -C "$ROOT/programming" -j"$JOBS" MF_CONFIG="$CONFIG"

if [[ "$CONFIG" == "debug" ]]; then
  OUTPUT="$ROOT/game/bin/server/el7_debug/server"
else
  OUTPUT="$ROOT/game/bin/server/el7/server"
fi

echo "Build finished. Server executables should be in: $OUTPUT"
