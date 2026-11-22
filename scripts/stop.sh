#!/usr/bin/env bash
# Stop servers started with: bash scripts/run.sh --detach
set -Eeuo pipefail
# shellcheck source=scripts/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

stopped=0
for name in frontend backend; do
  pidfile="$RUN_DIR/$name.pid"
  [ -f "$pidfile" ] || continue
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null || true
    ok "stopped $name (pid $pid)"
    stopped=1
  fi
  rm -f "$pidfile"
done
[ "$stopped" -eq 1 ] || info "nothing to stop"
