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
if [[ "$PLATFORM_CONFIG" == "el7_debug" ]]; then
  BUILD_CONFIG="debug"
else
  BUILD_CONFIG="hybrid"
fi
COMPONENTS=(dbappmgr cellappmgr baseappmgr loginapp dbapp cellapp serviceapp baseapp)

if [[ ! -d "$SERVER_DIR" ]]; then
  echo "ERROR: server binaries are missing: $SERVER_DIR" >&2
  echo "       Build with tools/build_server.sh $BUILD_CONFIG." >&2
  exit 1
fi

for component in "${COMPONENTS[@]}"; do
  if [[ ! -x "$SERVER_DIR/$component" ]]; then
    echo "ERROR: missing executable: $SERVER_DIR/$component" >&2
    exit 1
  fi
done

mkdir -p "$RUN_DIR"
cd "$GAME_DIR"

for component in "${COMPONENTS[@]}"; do
  pid_file="$RUN_DIR/$component.pid"
  if [[ -r "$pid_file" ]]; then
    old_pid="$(cat "$pid_file")"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
      process_exe="$(readlink -f "/proc/$old_pid/exe" 2>/dev/null || true)"
      expected_exe="$(readlink -f "$SERVER_DIR/$component")"
      if [[ "$process_exe" == "$expected_exe" ]]; then
        echo "$component already running (pid $old_pid)"
        continue
      fi
    fi
    rm -f "$pid_file"
  fi

  nohup "$SERVER_DIR/$component" \
    >"$RUN_DIR/$component.log" 2>&1 </dev/null &
  pid=$!
  echo "$pid" > "$pid_file"
  echo "started $component (pid $pid); log: $RUN_DIR/$component.log"
done

echo "Server processes started for $PLATFORM_CONFIG. Ensure bwmachined2 is running and the resource path selects game/res/tankarena/server/bw.xml."
