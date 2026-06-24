#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

usage() {
  cat <<'EOF'
Usage:
  ./run_server.sh [--build] [port]

Builds (optional) and runs the CompPrehension Toolchain Server JSON-RPC jar.

Options:
  --build       Run `mvn -DskipTests package` in the server project before launching.
  port          Port to listen on (overrides JSON_RPC_TOOLCHAIN_PORT / default 8080).
  -h, --help    Show this help.

.env variables:
  TOOLCHAIN_SERVER_PATH            Path to the compph-toolchain-server project root (required).
                                   The runnable jar is looked up under <root>/target.
  JSON_RPC_TOOLCHAIN_PORT          Port to listen on (default 8080).
  JSON_RPC_TOOLCHAIN_HOST          Bind address (default 0.0.0.0).
  JSON_RPC_TOOLCHAIN_ACCESS_SECRET Shared secret; exported to the server as ACCESS_SECRET.
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

load_env

do_build=0
port_override=""
for arg in "$@"; do
  case "${arg}" in
    -h|--help|help)
      usage
      exit 0
      ;;
    --build)
      do_build=1
      ;;
    *)
      port_override="${arg}"
      ;;
  esac
done

server_path="${TOOLCHAIN_SERVER_PATH:-}"
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

target_dir="${server_path}/target"
if [[ ! -d "${target_dir}" ]]; then
  echo "No target/ directory in ${server_path}. Build first with: ./run_server.sh --build" >&2
  exit 1
fi

# Pick the runnable fat jar (exclude the shade plugin's original-*.jar and sources/javadoc jars).
jar=""
while IFS= read -r candidate; do
  jar="${candidate}"
  break
done < <(find "${target_dir}" -maxdepth 1 -type f -name '*.jar' \
  ! -name 'original-*' ! -name '*-sources.jar' ! -name '*-javadoc.jar' | sort)

if [[ -z "${jar}" ]]; then
  echo "No runnable jar found in ${target_dir}. Build first with: ./run_server.sh --build" >&2
  exit 1
fi

port="${port_override:-${JSON_RPC_TOOLCHAIN_PORT:-8080}}"
export HOST="${JSON_RPC_TOOLCHAIN_HOST:-0.0.0.0}"
export PORT="${port}"
if [[ -n "${JSON_RPC_TOOLCHAIN_ACCESS_SECRET:-}" ]]; then
  export ACCESS_SECRET="${JSON_RPC_TOOLCHAIN_ACCESS_SECRET}"
fi

echo "==> Starting toolchain server"
echo "    jar:  ${jar}"
echo "    bind: ${HOST}:${port}"
exec java -jar "${jar}" "${port}"
