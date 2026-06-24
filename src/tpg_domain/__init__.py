"""tpg_domain facade.

Re-exports the public API bound to the active backend (``cli`` by default, ``rpc`` when configured
via ``TOOLCHAIN_BACKEND``/``TPG_BACKEND``). The CLI and JSON-RPC implementations live in
:mod:`src.tpg_domain.cli` and :mod:`src.tpg_domain.rpc`; the shared data model lives in
:mod:`src.tpg_domain.models`. All three stay importable directly.
"""

from src.env import TPG_BACKEND_ENV_VAR, select_backend

from . import cli
from .models import (
    DomainBuildMethod,
    ExpressionQueryResult,
    ReasoningException,
    ReasoningResult,
    ReasoningTrace,
    TpgProject,
    parse_expression_query_jsonl,
    parse_reasoning_jsonl,
)

_backend = select_backend(TPG_BACKEND_ENV_VAR)
if _backend == "rpc":
    from . import rpc as _impl
else:
    _impl = cli

#: Name of the backend selected at import time ("cli" or "rpc").
ACTIVE_BACKEND = _backend

validate_domain_solving_model = _impl.validate_domain_solving_model
validate_domain_loqi = _impl.validate_domain_loqi
tree_loqi_to_xml = _impl.tree_loqi_to_xml
domain_to_rdf = _impl.domain_to_rdf
rdf_to_domain_loqi = _impl.rdf_to_domain_loqi
solve_reasoning = _impl.solve_reasoning
solve_reasoning_result = _impl.solve_reasoning_result
query_expression = _impl.query_expression

__all__ = [
    "ACTIVE_BACKEND",
    "DomainBuildMethod",
    "ExpressionQueryResult",
    "ReasoningException",
    "ReasoningResult",
    "ReasoningTrace",
    "TpgProject",
    "domain_to_rdf",
    "parse_expression_query_jsonl",
    "parse_reasoning_jsonl",
    "query_expression",
    "rdf_to_domain_loqi",
    "solve_reasoning",
    "solve_reasoning_result",
    "tree_loqi_to_xml",
    "validate_domain_loqi",
    "validate_domain_solving_model",
]
