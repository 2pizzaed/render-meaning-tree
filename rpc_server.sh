#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
PID_FILE="${SCRIPT_DIR}/.rpc_pid"
LOG_FILE="${SCRIPT_DIR}/.rpc_server.log"
RUNNING_PID=""
RUNNING_SOURCE=""

usage() {
  cat <<'EOF'
Usage:
  ./rpc_server.sh start [--build] [port]
  ./rpc_server.sh stop
  ./rpc_server.sh status

Commands:
  start         Build (optional) and launch the RPC server as a background daemon.
  stop          Stop the running daemon (using the PID saved in .rpc_pid).
  status        Check whether the daemon is running or listening on the configured port.
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

server_port() {
  printf '%s\n' "${JSON_RPC_TOOLCHAIN_PORT:-8080}"
}

process_running() {
  local pid="$1"
  if [[ -z "${pid}" ]]; then
    return 1
  fi
  if kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command \
      "if (Get-Process -Id ${pid} -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" \
      >/dev/null 2>&1
    return $?
  fi
  return 1
}

listener_pid_for_port() {
  local port="$1"
  local pid=""

  if command -v ss >/dev/null 2>&1; then
    pid="$(ss -H -ltnp "sport = :${port}" 2>/dev/null \
      | sed -nE 's/.*pid=([0-9]+).*/\1/p' \
      | head -n 1)"
    if [[ -n "${pid}" ]]; then
      printf '%s\n' "${pid}"
      return 0
    fi
  fi

  if command -v lsof >/dev/null 2>&1; then
    pid="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -n 1)"
    if [[ -n "${pid}" ]]; then
      printf '%s\n' "${pid}"
      return 0
    fi
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    pid="$(powershell.exe -NoProfile -Command \
      "(Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)" \
      2>/dev/null | tr -d '\r' | head -n 1)"
    if [[ -n "${pid}" ]]; then
      printf '%s\n' "${pid}"
      return 0
    fi
  fi

  return 1
}

stop_process() {
  local pid="$1"
  kill "${pid}" 2>/dev/null || true

  local waited=0
  while process_running "${pid}" && (( waited < 5 )); do
    sleep 1
    (( waited++ )) || true
  done

  if process_running "${pid}"; then
    if ! kill -9 "${pid}" 2>/dev/null; then
      if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command \
          "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue" \
          >/dev/null 2>&1 || true
      fi
    fi
  fi
}

is_running() {
  RUNNING_PID=""
  RUNNING_SOURCE=""

  local port
  port="$(server_port)"
  local listener_pid=""
  listener_pid="$(listener_pid_for_port "${port}" || true)"
  if [[ -n "${listener_pid}" ]]; then
    RUNNING_PID="${listener_pid}"
    RUNNING_SOURCE="port-listener"
    if [[ -f "${PID_FILE}" ]] && [[ "$(cat "${PID_FILE}")" == "${listener_pid}" ]]; then
      RUNNING_SOURCE="pid-file"
    else
      echo "${listener_pid}" > "${PID_FILE}"
    fi
    return 0
  fi

  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if process_running "${pid}"; then
      RUNNING_PID="${pid}"
      RUNNING_SOURCE="pid-file-no-listener"
      return 0
    fi
    rm -f "${PID_FILE}"
  fi

  return 1
}

# --------------------------------------------------------------------------

cmd_start() {
  if is_running; then
    echo "RPC server is already running (PID ${RUNNING_PID}, ${RUNNING_SOURCE}, port $(server_port))."
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
  if ! is_running; then
    echo "RPC server is not running."
    rm -f "${PID_FILE}"
    exit 0
  fi

  local pid
  pid="${RUNNING_PID}"

  echo "==> Stopping toolchain server (PID ${pid}, ${RUNNING_SOURCE}, port $(server_port))"
  stop_process "${pid}"
  if process_running "${pid}"; then
    echo "    Forcing kill..."
    stop_process "${pid}"
  fi

  rm -f "${PID_FILE}"
  echo "Server stopped."
}

cmd_status() {
  if is_running; then
    echo "RPC server is running (PID ${RUNNING_PID}, ${RUNNING_SOURCE}, port $(server_port))."
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
