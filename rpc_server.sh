#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
PID_FILE="${SCRIPT_DIR}/.rpc_pid"
LOG_FILE="${SCRIPT_DIR}/.rpc_server.log"

usage() {
  cat <<'EOF'
Usage:
  ./rpc_server.sh start [--build] [port]
  ./rpc_server.sh stop
  ./rpc_server.sh status

Commands:
  start         Build (optional) and launch the RPC server as a background daemon.
  stop          Stop the running daemon (using the PID saved in .rpc_pid).
  status        Check whether the daemon is running.
  -h, --help    Show this help.

Start options:
  --build       Run `mvn -DskipTests package` before launching.
  port          Port override (otherwise JSON_RPC_TOOLCHAIN_PORT or 8080).

.env variables:
  TOOLCHAIN_SERVER_PATH            Path to the compph-toolchain-server project root (required).
  JSON_RPC_TOOLCHAIN_PORT          Port (default 8080).
  JSON_RPC_TOOLCHAIN_HOST          Bind address (default 0.0.0.0).
  JSON_RPC_TOOLCHAIN_ACCESS_SECRET Shared secret; forwarded to the server as ACCESS_SECRET.
EOF
}

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
  fi
}

resolve_path() {
  local path="$1"
  if [[ "${path}" == "~"* ]]; then
    path="${HOME}${path:1}"
  elif [[ "${path}" != /* && ! "${path}" =~ ^[A-Za-z]:[\\/] ]]; then
    path="${SCRIPT_DIR}/${path}"
  fi
  printf '%s\n' "${path}"
}

find_jar() {
  local target_dir="$1"
  local jar=""
  while IFS= read -r candidate; do
    jar="${candidate}"
    break
  done < <(find "${target_dir}" -maxdepth 1 -type f -name '*.jar' \
    ! -name 'original-*' ! -name '*-sources.jar' ! -name '*-javadoc.jar' | sort)
  printf '%s\n' "${jar}"
}

is_running() {
  if [[ ! -f "${PID_FILE}" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "${PID_FILE}")"
  if kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  rm -f "${PID_FILE}"
  return 1
}

# --------------------------------------------------------------------------

cmd_start() {
  if is_running; then
    local pid
    pid="$(cat "${PID_FILE}")"
    echo "RPC server is already running (PID ${pid})."
    echo "Stop it first with: ./rpc_server.sh stop"
    exit 1
  fi

  local do_build=0
  local port_override=""
  for arg in "$@"; do
    case "${arg}" in
      --build) do_build=1 ;;
      *)       port_override="${arg}" ;;
    esac
  done

  local server_path="${TOOLCHAIN_SERVER_PATH:-}"
  if [[ -z "${server_path}" ]]; then
    echo "Missing TOOLCHAIN_SERVER_PATH. Set it in ${ENV_FILE}." >&2
    exit 1
  fi
  server_path="$(resolve_path "${server_path}")"
  if [[ ! -f "${server_path}/pom.xml" ]]; then
    echo "TOOLCHAIN_SERVER_PATH has no pom.xml: ${server_path}" >&2
    exit 1
  fi

  if [[ "${do_build}" == "1" ]]; then
    echo "==> Building toolchain server"
    echo "    ${server_path}"
    (cd "${server_path}" && mvn -DskipTests package)
  fi

  local target_dir="${server_path}/target"
  if [[ ! -d "${target_dir}" ]]; then
    echo "No target/ directory in ${server_path}. Build first with: ./rpc_server.sh start --build" >&2
    exit 1
  fi

  local jar
  jar="$(find_jar "${target_dir}")"
  if [[ -z "${jar}" ]]; then
    echo "No runnable jar found in ${target_dir}. Build first with: ./rpc_server.sh start --build" >&2
    exit 1
  fi

  local port="${port_override:-${JSON_RPC_TOOLCHAIN_PORT:-8080}}"
  export HOST="${JSON_RPC_TOOLCHAIN_HOST:-0.0.0.0}"
  export PORT="${port}"
  if [[ -n "${JSON_RPC_TOOLCHAIN_ACCESS_SECRET:-}" ]]; then
    export ACCESS_SECRET="${JSON_RPC_TOOLCHAIN_ACCESS_SECRET}"
  fi

  export DOTENV_PATH="${server_path}/.env"

  echo "==> Starting toolchain server (daemon)"
  echo "    jar:  ${jar}"
  echo "    bind: ${HOST}:${port}"
  echo "    log:  ${LOG_FILE}"

  nohup java -jar "${jar}" "${port}" > "${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" > "${PID_FILE}"
  echo "    PID:  ${pid}"

  sleep 1
  if ! kill -0 "${pid}" 2>/dev/null; then
    echo "Server process exited immediately. Check ${LOG_FILE} for details." >&2
    rm -f "${PID_FILE}"
    exit 1
  fi

  echo "Server started. Stop with: ./rpc_server.sh stop"
}

cmd_stop() {
  if [[ ! -f "${PID_FILE}" ]]; then
    echo "No .rpc_pid file found — server is not running (or was not started by this script)."
    exit 0
  fi

  local pid
  pid="$(cat "${PID_FILE}")"

  if ! kill -0 "${pid}" 2>/dev/null; then
    echo "PID ${pid} is not running (stale .rpc_pid). Cleaning up."
    rm -f "${PID_FILE}"
    exit 0
  fi

  echo "==> Stopping toolchain server (PID ${pid})"
  kill "${pid}" 2>/dev/null || true

  local waited=0
  while kill -0 "${pid}" 2>/dev/null && (( waited < 5 )); do
    sleep 1
    (( waited++ )) || true
  done

  if kill -0 "${pid}" 2>/dev/null; then
    echo "    Forcing kill..."
    kill -9 "${pid}" 2>/dev/null || true
  fi

  rm -f "${PID_FILE}"
  echo "Server stopped."
}

cmd_status() {
  if is_running; then
    local pid
    pid="$(cat "${PID_FILE}")"
    echo "RPC server is running (PID ${pid})."
  else
    echo "RPC server is not running."
  fi
}

# --------------------------------------------------------------------------

load_env

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

command="$1"
shift

case "${command}" in
  start)   cmd_start "$@" ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  -h|--help|help) usage ;;
  *)
    echo "Unknown command: ${command}" >&2
    usage >&2
    exit 1
    ;;
esac
