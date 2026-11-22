#!/usr/bin/env bash
# Rootwise: start the backend (FastAPI) and frontend (Next.js) together.
#
#   bash scripts/run.sh              # dev servers with hot reload, logs streamed here, Ctrl-C stops both
#   bash scripts/run.sh --prod       # production frontend build + backend without reload
#   bash scripts/run.sh --detach     # run in the background; stop with: bash scripts/stop.sh
#
# Ports/host: BACKEND_PORT (8000), FRONTEND_PORT (3000), HOST (127.0.0.1; use 0.0.0.0 to expose).
set -Eeuo pipefail
# shellcheck source=scripts/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

MODE=dev; DETACH=0
HOST="${HOST:-127.0.0.1}"; BACKEND_PORT="${BACKEND_PORT:-8000}"; FRONTEND_PORT="${FRONTEND_PORT:-3000}"
while [ $# -gt 0 ]; do
  case "$1" in
    --prod) MODE=prod; shift ;;
    --dev) MODE=dev; shift ;;
    --detach|-d) DETACH=1; shift ;;
    --host) HOST="${2:?}"; shift 2 ;;
    --backend-port) BACKEND_PORT="${2:?}"; shift 2 ;;
    --frontend-port) FRONTEND_PORT="${2:?}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

load_toolchain_paths
have uv && node_ok && [ -d "$BACKEND/.venv" ] && [ -d "$FRONTEND/node_modules" ] || die "not set up yet: run  bash scripts/setup.sh"
mkdir -p "$LOG_DIR" "$RUN_DIR"
[ -f "$RUN_DIR/backend.pid" ] && kill -0 "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null && die "already running (bash scripts/stop.sh first)"
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then die "port $p is already in use (set BACKEND_PORT / FRONTEND_PORT)"; fi
done

# The browser needs the API URL; CORS must allow the frontend origin.
API_URL="$(get_env "$FRONTEND/.env.local" NEXT_PUBLIC_API_URL)"
API_URL="${API_URL:-http://localhost:$BACKEND_PORT}"
export NEXT_PUBLIC_API_URL="$API_URL"
cors="$(get_env "$BACKEND/.env" CORS_ORIGINS)"
export CORS_ORIGINS="${cors:+$cors,}http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"

launch() {  # name, workdir, command...  -> own process group, so stop kills the whole tree
  local name="$1" dir="$2"; shift 2
  : >"$LOG_DIR/$name.log"
  (cd "$dir" && exec setsid "$@" >>"$LOG_DIR/$name.log" 2>&1) &
  echo $! >"$RUN_DIR/$name.pid"
}

stop_all() {
  trap - INT TERM EXIT
  printf '\n'; info "stopping…"
  for name in frontend backend; do
    if [ -f "$RUN_DIR/$name.pid" ]; then
      pid="$(cat "$RUN_DIR/$name.pid")"
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
      rm -f "$RUN_DIR/$name.pid"
    fi
  done
  [ -n "${TAIL_PID:-}" ] && kill "$TAIL_PID" 2>/dev/null || true
  ok "stopped"
}

step "Backend  ($MODE)  http://$HOST:$BACKEND_PORT"
if [ "$MODE" = dev ]; then
  launch backend "$BACKEND" uv run uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" --reload
else
  launch backend "$BACKEND" uv run uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" --proxy-headers
fi
[ "$DETACH" -eq 1 ] || trap stop_all INT TERM EXIT
wait_for_url "http://127.0.0.1:$BACKEND_PORT/health" backend 90 || { tail -n 40 "$LOG_DIR/backend.log"; die "backend did not start (logs/backend.log)"; }
ok "healthy: $(curl -fsS "http://127.0.0.1:$BACKEND_PORT/health")"

step "Frontend ($MODE)  http://$HOST:$FRONTEND_PORT"
if [ "$MODE" = prod ]; then
  built_api="$(cat "$FRONTEND/.next/.rootwise-api-url" 2>/dev/null || true)"
  if [ ! -f "$FRONTEND/.next/BUILD_ID" ] || [ "$built_api" != "$API_URL" ]; then
    info "building the frontend for $API_URL (first run or API URL changed)…"
    pnpm_cmd build >"$LOG_DIR/frontend-build.log" 2>&1 || { tail -n 30 "$LOG_DIR/frontend-build.log"; die "frontend build failed"; }
    echo "$API_URL" >"$FRONTEND/.next/.rootwise-api-url"
  fi
  launch frontend "$FRONTEND" npx --yes "pnpm@$PNPM_VERSION" start --hostname "$HOST" --port "$FRONTEND_PORT"
else
  launch frontend "$FRONTEND" npx --yes "pnpm@$PNPM_VERSION" dev --hostname "$HOST" --port "$FRONTEND_PORT"
fi
wait_for_url "http://127.0.0.1:$FRONTEND_PORT/" frontend 180 || { tail -n 40 "$LOG_DIR/frontend.log"; die "frontend did not start (logs/frontend.log)"; }
ok "ready"

shown_host="$HOST"; [ "$HOST" = "0.0.0.0" ] && shown_host="localhost"
printf '\n%sRootwise is running%s\n' "$C_GREEN" "$C_OFF"
printf '    Home       http://%s:%s\n' "$shown_host" "$FRONTEND_PORT"
printf '    Student    http://%s:%s/play\n' "$shown_host" "$FRONTEND_PORT"
printf '    Teacher    http://%s:%s/teacher\n' "$shown_host" "$FRONTEND_PORT"
printf '    Admin      http://%s:%s/admin\n' "$shown_host" "$FRONTEND_PORT"
printf '    API docs   http://%s:%s/docs\n' "$shown_host" "$BACKEND_PORT"
if [ "$(get_env "$BACKEND/.env" OTEL_ENABLED)" = "true" ]; then
  printf '    OpenObserve %s (credentials: deploy/openobserve/.env)\n' "$(get_env "$BACKEND/.env" OPENOBSERVE_UI_URL)"
fi
printf '    Logs       %s/\n' "$LOG_DIR"

if [ "$DETACH" -eq 1 ]; then
  printf '\nRunning in the background. Stop with: %sbash scripts/stop.sh%s\n' "$C_DIM" "$C_OFF"
  exit 0
fi
printf '\n%sPress Ctrl-C to stop both servers. Streaming logs:%s\n\n' "$C_DIM" "$C_OFF"
tail -n 0 -F "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log" &
TAIL_PID=$!
wait "$TAIL_PID"
