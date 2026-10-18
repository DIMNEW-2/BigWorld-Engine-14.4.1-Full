#!/usr/bin/env bash
set -euo pipefail

GAME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUESTED_CONFIG="${1:-${BW_CONFIG:-hybrid}}"

case "$REQUESTED_CONFIG" in
  hybrid|el7) PLATFORM_CONFIG="el7" ;;
  debug|el7_debug) PLATFORM_CONFIG="el7_debug" ;;
  *)
    echo "Usage: $0 [hybrid|debug|el7|el7_debug]" >&2
    exit 2
    ;;
esac

SERVER_DIR="$GAME_DIR/bin/server/$PLATFORM_CONFIG/server"
RUN_DIR="$GAME_DIR/bin/server/$PLATFORM_CONFIG/run"
COMPONENTS=(baseapp serviceapp cellapp dbapp loginapp baseappmgr cellappmgr dbappmgr)

if [[ ! -d "$RUN_DIR" ]]; then
  echo "No BigWorld run directory found for $PLATFORM_CONFIG."
  exit 0
fi

for component in "${COMPONENTS[@]}"; do
  pid_file="$RUN_DIR/$component.pid"
  [[ -r "$pid_file" ]] || continue
  pid="$(cat "$pid_file")"
  if ! [[ "$pid" =~ ^[0-9]+$ ]] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    continue
  fi

  process_exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
  expected_exe="$(readlink -f "$SERVER_DIR/$component")"
  if [[ "$process_exe" != "$expected_exe" ]]; then
    echo "Skipping $component: pid $pid is not this checkout's server process."
    rm -f "$pid_file"
    continue
  fi

  echo "stopping $component (pid $pid)"
  kill -TERM "$pid" 2>/dev/null || true
  for unused in $(seq 1 25); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "  $component did not stop cleanly; sending SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
done

echo "BigWorld server processes stopped. Logs remain in $RUN_DIR."
