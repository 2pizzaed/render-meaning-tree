from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import httpx

MEANING_TREE_CLI_DEBUG_ENV_VAR = "MEANING_TREE_CLI_DEBUG"
TPG_CLI_DEBUG_ENV_VAR = "TPG_CLI_DEBUG"

# Backend selection: "cli" (run the toolchain JARs as subprocesses), "rpc" (call the
# CompPrehension Toolchain Server over JSON-RPC), or "auto" (prefer a compatible RPC server and
# otherwise use the CLI). A global default plus optional per-tool overrides.
TOOLCHAIN_BACKEND_ENV_VAR = "TOOLCHAIN_BACKEND"
MEANING_TREE_BACKEND_ENV_VAR = "MEANING_TREE_BACKEND"
TPG_BACKEND_ENV_VAR = "TPG_BACKEND"

# JSON-RPC server connection (used when the backend is "rpc").
JSON_RPC_TOOLCHAIN_SERVER_ENV_VAR = "JSON_RPC_TOOLCHAIN_SERVER"
JSON_RPC_TOOLCHAIN_ACCESS_SECRET_ENV_VAR = "JSON_RPC_TOOLCHAIN_ACCESS_SECRET"

# When true, file_source(Path) and dir_source(Path) send {"path":"..."} instead of file contents.
# Requires LOCAL_FILES_DISCOVERY=true on the server. Only safe for local deployments.
TOOLCHAIN_LOCAL_FILES_ENV_VAR = "TOOLCHAIN_LOCAL_FILES"

DEFAULT_TOOLCHAIN_SERVER_URL = "http://localhost:8080"
AUTO_BACKEND_HEALTH_TIMEOUT_SECONDS = 1.0
_EXPECTED_SERVER_NAME = "compph-toolchain-server"
_EXPECTED_TOOL_ROUTES = {
    "its_DomainModel": "/rpc/domain",
    "its_Reasoner": "/rpc/reasoner",
    "meaning_tree": "/rpc/meaning-tree",
}

type Backend = Literal["cli", "rpc"]

_ENV_LOADED = False
_auto_rpc_tools: frozenset[str] | None = None

logger = logging.getLogger(__name__)


def env_flag(name: str) -> bool:
    load_project_env()
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def env_str(name: str, default: str | None = None) -> str | None:
    load_project_env()
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def select_backend(
    tool_override_var: str | None = None,
    *,
    required_rpc_tools: tuple[str, ...] = (),
) -> Backend:
    """Resolve the active backend for a tool: a per-tool override wins over the global default.

    Recognized values are ``cli``, ``rpc``, and ``auto`` (case-insensitive). In ``auto`` mode the
    server's ``/health`` endpoint is requested at most once per process. RPC is selected only when
    that endpoint identifies a compatible toolchain server and advertises *required_rpc_tools*.
    Anything else falls back to ``cli``.
    """
    raw: str | None = None
    if tool_override_var is not None:
        raw = env_str(tool_override_var)
    if raw is None:
        raw = env_str(TOOLCHAIN_BACKEND_ENV_VAR)
    normalized = (raw or "cli").strip().lower()
    if normalized == "rpc":
        return "rpc"
    if normalized == "auto":
        available_tools = _auto_available_rpc_tools()
        return "rpc" if set(required_rpc_tools).issubset(available_tools) else "cli"
    return "cli"


def toolchain_server_url() -> str:
    return env_str(JSON_RPC_TOOLCHAIN_SERVER_ENV_VAR, DEFAULT_TOOLCHAIN_SERVER_URL) or DEFAULT_TOOLCHAIN_SERVER_URL


def toolchain_access_secret() -> str | None:
    return env_str(JSON_RPC_TOOLCHAIN_ACCESS_SECRET_ENV_VAR)


def toolchain_local_files() -> bool:
    """True when file/dir sources should be sent as local path references instead of inline content."""
    return env_flag(TOOLCHAIN_LOCAL_FILES_ENV_VAR)


def _auto_available_rpc_tools() -> frozenset[str]:
    """Return tools advertised by the one-time health probe, or an empty set on failure."""
    global _auto_rpc_tools
    if _auto_rpc_tools is None:
        _auto_rpc_tools = _probe_toolchain_health()
    return _auto_rpc_tools


def _probe_toolchain_health() -> frozenset[str]:
    url = f"{toolchain_server_url().rstrip('/')}/health"
    try:
        response = httpx.get(url, timeout=AUTO_BACKEND_HEALTH_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Toolchain RPC health probe failed; using CLI backend: %s", exc)
        return frozenset()

    if not isinstance(payload, dict):
        logger.info("Toolchain RPC health probe returned a non-object payload; using CLI backend")
        return frozenset()
    if payload.get("status") != "ok" or payload.get("server") != _EXPECTED_SERVER_NAME:
        logger.info("Toolchain RPC health probe identified an incompatible server; using CLI backend")
        return frozenset()
    tools = payload.get("tools")
    if not isinstance(tools, list):
        logger.info("Toolchain RPC health probe returned no tool registry; using CLI backend")
        return frozenset()

    available_tools: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        route = tool.get("route")
        if isinstance(name, str) and route == _EXPECTED_TOOL_ROUTES.get(name):
            available_tools.add(name)
    return frozenset(available_tools)


def load_project_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = _find_project_env()
    if env_path is not None:
        _load_env_file(env_path)
    _ENV_LOADED = True


def _find_project_env() -> Path | None:
    for root in [Path.cwd(), *Path(__file__).resolve().parents]:
        env_path = root / ".env"
        if env_path.is_file():
            return env_path
    return None


def _load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        name, value = parsed
        os.environ.setdefault(name, value)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    name, value = stripped.split("=", 1)
    name = name.strip()
    if not name:
        return None

    value = _strip_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return name, value


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value
