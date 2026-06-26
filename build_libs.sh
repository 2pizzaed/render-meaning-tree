#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

usage() {
  cat <<'EOF'
Usage:
  ./rebuild_projects.sh [tpg|meaning_tree|mt]

Targets:
  tpg           Rebuild its_DomainModel, then its_Reasoner
  meaning_tree  Rebuild Meaning Tree
  mt            Alias for meaning_tree
  <empty>       Rebuild all projects: its_DomainModel, its_Reasoner, meaning_tree

.env variables:
  ITS_DOMAINMODEL_PATH  Path to its_DomainModel
  ITS_REASONER_PATH     Path to its_Reasoner
  MEANING_TREE_PATH     Path to meaning_tree; defaults to ./meaning_tree
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

first_non_empty() {
  local value
  for value in "$@"; do
    if [[ -n "${value}" ]]; then
      printf '%s\n' "${value}"
      return 0
    fi
  done
  return 1
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

require_project_dir() {
  local label="$1"
  local path="$2"

  if [[ -z "${path}" ]]; then
    echo "Missing path for ${label}. Set it in ${ENV_FILE}." >&2
    exit 1
  fi

  path="$(resolve_path "${path}")"
  if [[ ! -d "${path}" ]]; then
    echo "${label} directory does not exist: ${path}" >&2
    exit 1
  fi
  if [[ ! -f "${path}/pom.xml" ]]; then
    echo "${label} directory has no pom.xml: ${path}" >&2
    exit 1
  fi

  printf '%s\n' "${path}"
}

rebuild_project() {
  local label="$1"
  local path="$2"

  echo
  echo "==> Rebuilding ${label}"
  echo "    ${path}"
  (cd "${path}" && mvn clean install -DskipTests)
}

load_env

target="${1:-all}"
case "${target}" in
  -h|--help|help)
    usage
    exit 0
    ;;
  tpg|meaning_tree|mt|all)
    ;;
  *)
    echo "Unknown target: ${target}" >&2
    usage >&2
    exit 1
    ;;
esac

domain_model_path="$(first_non_empty "${ITS_DOMAINMODEL_PATH:-}" "${ITS_DOMAIN_MODEL_PATH:-}" "${DOMAINMODEL_PATH:-}" "${DOMAIN_MODEL_PATH:-}" || true)"
reasoner_path="$(first_non_empty "${ITS_REASONER_PATH:-}" "${REASONER_PATH:-}" || true)"
meaning_tree_path="$(first_non_empty "${MEANING_TREE_PATH:-}" "${MEANINGTREE_PATH:-}" || true)"
if [[ -z "${meaning_tree_path}" ]]; then
  meaning_tree_path="${SCRIPT_DIR}/meaning_tree"
fi

if [[ "${target}" == "all" || "${target}" == "tpg" ]]; then
  domain_model_path="$(require_project_dir "its_DomainModel" "${domain_model_path}")"
  reasoner_path="$(require_project_dir "its_Reasoner" "${reasoner_path}")"

  rebuild_project "its_DomainModel" "${domain_model_path}"
  rebuild_project "its_Reasoner" "${reasoner_path}"
fi

if [[ "${target}" == "all" || "${target}" == "meaning_tree" || "${target}" == "mt" ]]; then
  meaning_tree_path="$(require_project_dir "meaning_tree" "${meaning_tree_path}")"
  rebuild_project "meaning_tree" "${meaning_tree_path}"
fi
