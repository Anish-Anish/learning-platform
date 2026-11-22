# Shared helpers for setup.sh / run.sh / stop.sh. Sourced, not executed.
# shellcheck shell=bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/.run"
NODE_MAJOR_MIN=20
NODE_MINOR_MIN=9          # Next.js 16 needs Node >= 20.9
NODE_INSTALL_MAJOR=22
NVM_VERSION="v0.40.1"
# pnpm version pinned by frontend/package.json "packageManager"; run via npx so no global install is needed.
PNPM_VERSION="$(sed -n 's/.*"packageManager": *"pnpm@\([0-9][^"+]*\).*/\1/p' "$FRONTEND/package.json")"
export npm_config_update_notifier=false

if [ -t 1 ]; then
  C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'; C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_OFF=""
fi

step() { printf '\n%s==> %s%s\n' "$C_BLUE" "$*" "$C_OFF"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s✓%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '    %s!%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die()  { printf '%sError:%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# Make user-level installs (uv, nvm-managed node) visible to this shell.
load_toolchain_paths() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh" >/dev/null
    nvm use --silent "$NODE_INSTALL_MAJOR" >/dev/null 2>&1 || true
  fi
}

node_ok() {
  have node || return 1
  local v major minor
  v="$(node -v 2>/dev/null | sed 's/^v//')"
  major="${v%%.*}"; minor="$(echo "$v" | cut -d. -f2)"
  [ "$major" -gt "$NODE_MAJOR_MIN" ] || { [ "$major" -eq "$NODE_MAJOR_MIN" ] && [ "$minor" -ge "$NODE_MINOR_MIN" ]; }
}

pnpm_cmd() { (cd "$FRONTEND" && npx --yes "pnpm@$PNPM_VERSION" "$@"); }

# Set KEY=VALUE in an env file (adds or replaces; values may contain any characters).
set_env() {
  local file="$1" key="$2" value="$3"
  uv run --quiet --no-project python - "$file" "$key" "$value" <<'PY'
import pathlib, re, sys
path, key, value = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8") if path.exists() else ""
line = f"{key}={value}"
pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
text = pattern.sub(lambda _m: line, text, count=1) if pattern.search(text) else text.rstrip("\n") + ("\n" if text else "") + line + "\n"
path.write_text(text, encoding="utf-8")
PY
}

get_env() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 0
  grep -E "^${key}=" "$file" | tail -n1 | cut -d= -f2-
}

wait_for_url() {
  local url="$1" name="$2" timeout="${3:-120}" i
  for ((i = 0; i < timeout; i++)); do
    if curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}
