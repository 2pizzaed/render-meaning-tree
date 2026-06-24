"""meaning_tree facade.

Re-exports the public API bound to the active backend (``cli`` by default, ``rpc`` when configured
via ``TOOLCHAIN_BACKEND``/``MEANING_TREE_BACKEND``). The CLI and JSON-RPC implementations live in
:mod:`src.meaning_tree.cli` and :mod:`src.meaning_tree.rpc` and stay importable directly.
"""

from src.env import MEANING_TREE_BACKEND_ENV_VAR, select_backend

from . import cli
from .cli import DeserializationFormat, SerializationFormat

_backend = select_backend(MEANING_TREE_BACKEND_ENV_VAR)
if _backend == "rpc":
    from . import rpc as _impl
else:
    _impl = cli

#: Name of the backend selected at import time ("cli" or "rpc").
ACTIVE_BACKEND = _backend

to_dict = _impl.to_dict
to_dot = _impl.to_dot
to_tokens = _impl.to_tokens
convert = _impl.convert
generate = _impl.generate
node_hierarchy = _impl.node_hierarchy

__all__ = [
    "ACTIVE_BACKEND",
    "DeserializationFormat",
    "SerializationFormat",
    "convert",
    "generate",
    "node_hierarchy",
    "to_dict",
    "to_dot",
    "to_tokens",
]
