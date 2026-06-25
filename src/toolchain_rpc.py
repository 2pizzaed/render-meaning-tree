"""Thin JSON-RPC client for the CompPrehension Toolchain Server.

Used by the ``rpc`` backend of :mod:`src.meaning_tree` and :mod:`src.tpg_domain`. Talks to the
server documented in ``compph-toolchain-server`` (routes ``/rpc/meaning-tree``, ``/rpc/domain``,
``/rpc/reasoner``), packing file/directory inputs into the server's FileSource/DirSource payloads.
"""

from __future__ import annotations

import base64
import itertools
import logging
from pathlib import Path
from typing import Any

import httpx

from src.env import toolchain_access_secret, toolchain_local_files, toolchain_server_url

logger = logging.getLogger(__name__)

# File types the its_DomainModel / its_Reasoner directory inputs actually read. Packing only these
# keeps DirSource payloads small (see the server README).
MODEL_DIR_EXTENSIONS = frozenset({".loqi", ".xml", ".tpg", ".csv", ".ttl"})

DEFAULT_TIMEOUT_SECONDS = 600.0

_id_counter = itertools.count(1)


class RpcError(Exception):
    """Raised when the server returns a JSON-RPC error or the call cannot be completed."""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def call(route: str, method: str, params: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Invoke a JSON-RPC method and return its ``result`` (raises :class:`RpcError` on failure)."""
    url = _join(toolchain_server_url(), route)
    request = {
        "jsonrpc": "2.0",
        "id": next(_id_counter),
        "method": method,
        "params": params,
    }
    headers = {"Content-Type": "application/json"}
    secret = toolchain_access_secret()
    if secret:
        headers["X-Access-Secret"] = secret

    try:
        response = httpx.post(url, json=request, headers=headers, timeout=timeout)
    except httpx.ConnectError as exc:
        raise RpcError(
            f"Could not connect to the toolchain RPC server at {url}.\n"
            f"  Start it with:  ./rpc_server.sh start\n"
            f"  Or switch to CLI mode:  set TOOLCHAIN_BACKEND=cli in .env (not recommended, slower)\n"
            f"  Connection error: {exc}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RpcError(f"HTTP error talking to toolchain server at {url}: {exc}") from exc

    if response.status_code == 403:
        raise RpcError("Toolchain server returned 403 (missing or invalid access secret)", code=403)
    if response.status_code >= 400:
        raise RpcError(f"Toolchain server returned HTTP {response.status_code}: {response.text[:500]}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RpcError(f"Toolchain server returned non-JSON response: {response.text[:500]}") from exc

    error = payload.get("error")
    if error is not None:
        message = error.get("message", "unknown error")
        raise RpcError(f"{method} failed: {message}", code=error.get("code"), data=error.get("data"))
    return payload.get("result")


# -- payload builders ---------------------------------------------------------------------------


def file_source(content: str | bytes | Path) -> dict[str, str]:
    """Build a FileSource payload from inline text, raw bytes, or a path.

    When ``TOOLCHAIN_LOCAL_FILES=true`` and *content* is a :class:`~pathlib.Path`, sends
    ``{"path": str(content)}`` so the server reads the file directly (requires
    ``LOCAL_FILES_DISCOVERY=true`` on the server). Otherwise the file is read locally and its
    contents are embedded in the payload.
    """
    if isinstance(content, Path):
        if toolchain_local_files():
            return {"path": str(content)}
        return _bytes_to_source(content.read_bytes())
    if isinstance(content, bytes):
        return _bytes_to_source(content)
    return {"text": content}


def dir_source(
    directory: str | Path,
    *,
    extensions: frozenset[str] | None = MODEL_DIR_EXTENSIONS,
) -> dict[str, Any]:
    """Build a DirSource payload for a local directory.

    When ``TOOLCHAIN_LOCAL_FILES=true``, sends ``{"path": str(directory)}`` so the server reads
    the directory directly (requires ``LOCAL_FILES_DISCOVERY=true`` on the server). Otherwise
    packs files whose suffix is in *extensions* into ``{"files": {relpath: FileSource}}`` (pass
    ``extensions=None`` to include every file).
    """
    base = Path(directory)
    if not base.is_dir():
        raise RpcError(f"Directory does not exist: {base}")
    if toolchain_local_files():
        return {"path": str(base)}
    files: dict[str, dict[str, str]] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if extensions is not None and path.suffix.lower() not in extensions:
            continue
        rel = path.relative_to(base).as_posix()
        files[rel] = _bytes_to_source(path.read_bytes())
    if not files:
        raise RpcError(f"No packable files found in directory: {base}")
    return {"files": files}


def _bytes_to_source(data: bytes) -> dict[str, str]:
    try:
        return {"text": data.decode("utf-8")}
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(data).decode("ascii")}


def _join(base_url: str, route: str) -> str:
    return f"{base_url.rstrip('/')}/{route.lstrip('/')}"
