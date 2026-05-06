from __future__ import annotations

import os
from pathlib import Path

MEANING_TREE_CLI_DEBUG_ENV_VAR = "MEANING_TREE_CLI_DEBUG"
TPG_CLI_DEBUG_ENV_VAR = "TPG_CLI_DEBUG"

_ENV_LOADED = False


def env_flag(name: str) -> bool:
    load_project_env()
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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
