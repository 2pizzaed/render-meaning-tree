from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

MEANING_TREE_CLI_DEBUG_ENV_VAR = "MEANING_TREE_CLI_DEBUG"
TPG_CLI_DEBUG_ENV_VAR = "TPG_CLI_DEBUG"

# Backend selection: "cli" (run the toolchain JARs as subprocesses, the default) or
# "rpc" (call the CompPrehension Toolchain Server over JSON-RPC). A global default plus
# optional per-tool overrides.
TOOLCHAIN_BACKEND_ENV_VAR = "TOOLCHAIN_BACKEND"
MEANING_TREE_BACKEND_ENV_VAR = "MEANING_TREE_BACKEND"
TPG_BACKEND_ENV_VAR = "TPG_BACKEND"

# JSON-RPC server connection (used when the backend is "rpc").
JSON_RPC_TOOLCHAIN_SERVER_ENV_VAR = "JSON_RPC_TOOLCHAIN_SERVER"
JSON_RPC_TOOLCHAIN_ACCESS_SECRET_ENV_VAR = "JSON_RPC_TOOLCHAIN_ACCESS_SECRET"

DEFAULT_TOOLCHAIN_SERVER_URL = "http://localhost:8080"

type Backend = Literal["cli", "rpc"]

_ENV_LOADED = False


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


def select_backend(tool_override_var: str | None = None) -> Backend:
    """Resolve the active backend for a tool: a per-tool override wins over the global default.

    Recognized values are ``cli`` and ``rpc`` (case-insensitive). Anything else falls back to ``cli``.
    """
    raw: str | None = None
    if tool_override_var is not None:
        raw = env_str(tool_override_var)
    if raw is None:
        raw = env_str(TOOLCHAIN_BACKEND_ENV_VAR)
    normalized = (raw or "cli").strip().lower()
    return "rpc" if normalized == "rpc" else "cli"


def toolchain_server_url() -> str:
    return env_str(JSON_RPC_TOOLCHAIN_SERVER_ENV_VAR, DEFAULT_TOOLCHAIN_SERVER_URL) or DEFAULT_TOOLCHAIN_SERVER_URL


def toolchain_access_secret() -> str | None:
    return env_str(JSON_RPC_TOOLCHAIN_ACCESS_SECRET_ENV_VAR)


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
