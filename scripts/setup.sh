#!/usr/bin/env bash
# Rootwise: one-shot setup for Linux (Ubuntu/Debian, Fedora/RHEL, Arch, openSUSE, Alpine, WSL).
# Safe to re-run: every step checks what is already there.
#
#   bash scripts/setup.sh                      # offline AI mode (deterministic fallbacks), dev-ready
#   bash scripts/setup.sh --openai-key sk-...  # enable live AI features
#   bash scripts/setup.sh --with-observability # also start OpenObserve (Docker) and enable OpenTelemetry
#
# Afterwards: bash scripts/run.sh
set -Eeuo pipefail
# shellcheck source=scripts/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
trap 'die "setup failed at line $LINENO (see output above)"' ERR

usage() {
  cat <<EOF
Usage: bash scripts/setup.sh [options]

  --openai-key KEY        write OPENAI_API_KEY into backend/.env (leave out for offline mode)
  --api-url URL           public URL of the backend as seen by browsers (default: http://localhost:8000)
  --frontend-url URL      public URL of the frontend, added to the backend's CORS list
  --with-observability    run OpenObserve in Docker and export traces/metrics/logs to it
  --skip-tests            don't run the backend test suite
  --skip-build            don't build the production frontend (dev mode still works)
  --reset-db              delete backend/rootwise.db and reseed
  -y, --yes               install missing system packages without asking
  -h, --help              show this help
EOF
}

OPENAI_KEY=""; API_URL=""; FRONTEND_URL=""; WITH_OBS=0; SKIP_TESTS=0; SKIP_BUILD=0; RESET_DB=0; ASSUME_YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --openai-key) OPENAI_KEY="${2:?--openai-key needs a value}"; shift 2 ;;
    --api-url) API_URL="${2:?--api-url needs a value}"; shift 2 ;;
    --frontend-url) FRONTEND_URL="${2:?--frontend-url needs a value}"; shift 2 ;;
    --with-observability) WITH_OBS=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --reset-db) RESET_DB=1; shift ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "unknown option: $1" ;;
  esac
done

[ "$(uname -s)" = "Linux" ] || die "this script targets Linux (on Windows use WSL; on macOS install uv, Node 22 and pnpm manually)"

# ------------------------------------------------------------------ 1. system packages
step "1/7  System packages"
need_pkgs=()
for bin in curl tar xz git; do have "$bin" || need_pkgs+=("$bin"); done
[ -f /etc/ssl/certs/ca-certificates.crt ] || [ -d /etc/pki/tls/certs ] || need_pkgs+=("ca-certificates")
if [ ${#need_pkgs[@]} -gt 0 ]; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then have sudo && SUDO="sudo" || die "missing ${need_pkgs[*]} and no sudo; install them and re-run"; fi
  if have apt-get; then pm=(apt-get install -y); pkgs=(curl ca-certificates tar xz-utils git); $SUDO apt-get update -qq
  elif have dnf; then pm=(dnf install -y); pkgs=(curl ca-certificates tar xz git)
  elif have yum; then pm=(yum install -y); pkgs=(curl ca-certificates tar xz git)
  elif have pacman; then pm=(pacman -Sy --noconfirm); pkgs=(curl ca-certificates tar xz git)
  elif have zypper; then pm=(zypper install -y); pkgs=(curl ca-certificates tar xz git)
  elif have apk; then pm=(apk add); pkgs=(curl ca-certificates tar xz git bash libstdc++)
  else die "no supported package manager found; install: ${need_pkgs[*]}"
  fi
  if [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
    read -r -p "    Install ${pkgs[*]} with ${pm[0]}? [Y/n] " answer
    [[ "${answer:-Y}" =~ ^[Yy]$ ]] || die "cannot continue without: ${need_pkgs[*]}"
  fi
  DEBIAN_FRONTEND=noninteractive $SUDO "${pm[@]}" "${pkgs[@]}" >/dev/null
  ok "installed ${pkgs[*]}"
else
  ok "curl, tar, xz, git, CA certificates present"
fi
load_toolchain_paths

# ------------------------------------------------------------------ 2. uv + Python
step "2/7  Python toolchain (uv)"
if ! have uv; then
  info "installing uv (user-level, ~/.local/bin)"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
  load_toolchain_paths
fi
have uv || die "uv installation failed"
ok "uv $(uv --version | awk '{print $2}')"
uv python install --quiet "$(cat "$BACKEND/.python-version")"
ok "Python $(cat "$BACKEND/.python-version") available"

# ------------------------------------------------------------------ 3. Node + pnpm
step "3/7  Node.js + pnpm"
if ! node_ok; then
  info "installing Node $NODE_INSTALL_MAJOR with nvm $NVM_VERSION (user-level, ~/.nvm)"
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VERSION/install.sh" | PROFILE=/dev/null bash >/dev/null
  fi
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm install "$NODE_INSTALL_MAJOR" >/dev/null 2>&1
  nvm alias default "$NODE_INSTALL_MAJOR" >/dev/null
  load_toolchain_paths
fi
node_ok || die "Node >= $NODE_MAJOR_MIN.$NODE_MINOR_MIN is required (found: $(node -v 2>/dev/null || echo none))"
ok "Node $(node -v)"
[ -n "$PNPM_VERSION" ] || die "could not read the pnpm version from frontend/package.json"
ok "pnpm $(pnpm_cmd --version) (pinned in frontend/package.json)"

# ------------------------------------------------------------------ 4. backend
step "4/7  Backend dependencies + configuration"
(cd "$BACKEND" && uv sync --frozen --quiet)
ok "Python dependencies installed (backend/.venv)"
ENV_FILE="$BACKEND/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$BACKEND/.env.example" "$ENV_FILE"
  ok "created backend/.env from .env.example"
else
  ok "keeping existing backend/.env"
fi
[ -n "$OPENAI_KEY" ] && { set_env "$ENV_FILE" OPENAI_API_KEY "$OPENAI_KEY"; ok "OPENAI_API_KEY set"; }
if [ -n "$FRONTEND_URL" ]; then
  cors="$(get_env "$ENV_FILE" CORS_ORIGINS)"
  case ",$cors," in *",$FRONTEND_URL,"*) ;; *) set_env "$ENV_FILE" CORS_ORIGINS "${cors:+$cors,}$FRONTEND_URL" ;; esac
  ok "CORS allows $FRONTEND_URL"
fi
if [ -n "$(get_env "$ENV_FILE" OPENAI_API_KEY)" ]; then ok "AI mode: online"; else warn "AI mode: offline (no OPENAI_API_KEY); re-run with --openai-key to enable live AI"; fi

# ------------------------------------------------------------------ 5. database
step "5/7  Database"
if [ "$RESET_DB" -eq 1 ]; then rm -f "$BACKEND"/rootwise.db "$BACKEND"/rootwise.db-*; info "removed existing database"; fi
(cd "$BACKEND" && uv run --quiet python -m app.db.seed | tail -n1)
ok "seed content loaded (built-in Data Structures course)"
if [ "$SKIP_TESTS" -eq 0 ]; then
  info "running backend tests (use --skip-tests to skip)"
  (cd "$BACKEND" && uv run --quiet pytest -q -p no:cacheprovider 2>&1 | grep -v '^{"' | tail -n 3)
  ok "backend tests passed"
fi

# ------------------------------------------------------------------ 6. frontend
step "6/7  Frontend dependencies"
pnpm_cmd install --frozen-lockfile >/dev/null
ok "Node dependencies installed (frontend/node_modules)"
API_URL="${API_URL:-$(get_env "$FRONTEND/.env.local" NEXT_PUBLIC_API_URL)}"
API_URL="${API_URL:-http://localhost:8000}"
set_env "$FRONTEND/.env.local" NEXT_PUBLIC_API_URL "$API_URL"
ok "frontend talks to the API at $API_URL (frontend/.env.local)"
if [ "$SKIP_BUILD" -eq 0 ]; then
  info "building the production frontend (use --skip-build to skip)"
  pnpm_cmd build >"$ROOT/.setup-build.log" 2>&1 || { tail -n 30 "$ROOT/.setup-build.log"; die "frontend build failed"; }
  rm -f "$ROOT/.setup-build.log"
  echo "$API_URL" >"$FRONTEND/.next/.rootwise-api-url"
  ok "production build ready (frontend/.next)"
fi

# ------------------------------------------------------------------ 7. observability (optional)
step "7/7  Observability (OpenTelemetry -> OpenObserve)"
if [ "$WITH_OBS" -eq 1 ]; then
  have docker || die "--with-observability needs Docker (https://docs.docker.com/engine/install/)"
  docker compose version >/dev/null 2>&1 || die "--with-observability needs the Docker Compose plugin"
  OBS_ENV="$ROOT/deploy/openobserve/.env"
  if [ ! -f "$OBS_ENV" ]; then
    pw="$(uv run --quiet --no-project python -c 'import secrets,string; a=string.ascii_letters+string.digits; print("Rw"+"".join(secrets.choice(a) for _ in range(16))+"7a!")')"
    printf 'OPENOBSERVE_USER=root@rootwise.local\nOPENOBSERVE_PASSWORD=%s\n' "$pw" >"$OBS_ENV"
    chmod 600 "$OBS_ENV"
    ok "generated OpenObserve credentials in deploy/openobserve/.env"
  fi
  docker compose -f "$ROOT/deploy/openobserve/docker-compose.yml" up -d >/dev/null
  wait_for_url "http://localhost:5080/healthz" OpenObserve 90 || die "OpenObserve did not become healthy (docker logs rootwise-openobserve)"
  ok "OpenObserve running at http://localhost:5080"
  for kv in OTEL_ENABLED=true OTEL_EXPORTER_ENDPOINT=http://localhost:5080/api/default \
            OPENOBSERVE_UI_URL=http://localhost:5080 OPENOBSERVE_ORG=default \
            "OPENOBSERVE_USER=$(get_env "$OBS_ENV" OPENOBSERVE_USER)" \
            "OPENOBSERVE_PASSWORD=$(get_env "$OBS_ENV" OPENOBSERVE_PASSWORD)"; do
    set_env "$ENV_FILE" "${kv%%=*}" "${kv#*=}"
  done
  ok "OpenTelemetry export enabled in backend/.env"
else
  info "skipped (add --with-observability to run OpenObserve in Docker)"
fi

printf '\n%sSetup complete.%s Start everything with:\n\n    bash scripts/run.sh            %s# dev servers with hot reload%s\n    bash scripts/run.sh --prod     %s# production build%s\n\n' \
  "$C_GREEN" "$C_OFF" "$C_DIM" "$C_OFF" "$C_DIM" "$C_OFF"
