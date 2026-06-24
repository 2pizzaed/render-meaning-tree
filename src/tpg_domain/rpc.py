"""JSON-RPC backend for tpg_domain, mirroring :mod:`src.tpg_domain.cli`.

Public functions have identical signatures to the CLI backend but call the CompPrehension Toolchain
Server (routes ``/rpc/domain`` and ``/rpc/reasoner``). Directory arguments are packed into DirSource
payloads; file arguments are read and sent inline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TextIO

from src.toolchain_rpc import RpcError
from src.toolchain_rpc import call as _rpc_call
from src.toolchain_rpc import dir_source, file_source

from .models import (
    DomainBuildMethod,
    ExpressionQueryResult,
    ReasoningResult,
    _parse_reasoning_exception,
    _parse_reasoning_result_value,
)

DOMAIN_ROUTE = "/rpc/domain"
REASONER_ROUTE = "/rpc/reasoner"

logger = logging.getLogger(__name__)


def validate_domain_solving_model(
    model_dir: str | Path,
    build_method: DomainBuildMethod = "LOQI",
) -> bool:
    result = _safe_call(DOMAIN_ROUTE, "validate-dsm", {
        "model": dir_source(model_dir),
        "buildMethod": _build_method(build_method),
    })
    return result is not None


def validate_domain_loqi(
    domain_loqi: str | Path,
    model_dir: str | Path,
    tag: str | None = None,
    print_merged_loqi: bool = False,
) -> bool:
    params: dict[str, Any] = {
        "domainLoqi": file_source(Path(domain_loqi)),
        "model": dir_source(model_dir),
        "printMergedLoqi": print_merged_loqi,
    }
    _put(params, "tag", tag)
    return _safe_call(DOMAIN_ROUTE, "validate-domain-loqi", params) is not None


def tree_loqi_to_xml(
    tree_loqi: str | Path,
    *,
    output: str | Path | None = None,
    model_dir: str | Path | None = None,
    tag: str | None = None,
    cdata_expressions: bool = True,
) -> str | bool | None:
    params: dict[str, Any] = {
        "treeLoqi": file_source(Path(tree_loqi)),
        "useCDataExpressions": cdata_expressions,
    }
    if model_dir is not None:
        params["modelDir"] = dir_source(model_dir)
    _put(params, "tag", tag)
    result = _safe_call(DOMAIN_ROUTE, "tree-loqi-to-xml", params)
    return _text_or_bool(result, "xml", output)


def domain_to_rdf(
    model_dir: str | Path,
    *,
    build_method: DomainBuildMethod = "LOQI",
    tag: str | None = None,
    domain_loqi: str | Path | None = None,
    output: str | Path | None = None,
    base_prefix: str | None = None,
    old_nary_compat: bool = False,
) -> str | bool | None:
    params: dict[str, Any] = {
        "model": dir_source(model_dir),
        "buildMethod": _build_method(build_method),
        "oldNaryCompat": old_nary_compat,
    }
    _put(params, "tag", tag)
    _put(params, "basePrefix", base_prefix)
    if domain_loqi is not None:
        params["domainLoqi"] = file_source(Path(domain_loqi))
    result = _safe_call(DOMAIN_ROUTE, "domain-to-rdf", params)
    return _text_or_bool(result, "ttl", output)


def rdf_to_domain_loqi(
    model_dir: str | Path,
    rdf_ttl: str | Path,
    *,
    build_method: DomainBuildMethod = "LOQI",
    tag: str | None = None,
    domain_loqi: str | Path | None = None,
    output: str | Path | None = None,
    base_prefix: str | None = None,
    old_nary_compat: bool = False,
    throw_invalid_meta: bool = False,
    separate_metadata: bool = False,
    separate_class_property_values: bool = False,
) -> str | bool | None:
    params: dict[str, Any] = {
        "model": dir_source(model_dir),
        "rdfTtl": file_source(Path(rdf_ttl)),
        "buildMethod": _build_method(build_method),
        "oldNaryCompat": old_nary_compat,
        "throwInvalidMeta": throw_invalid_meta,
        "separateMetadata": separate_metadata,
        "separateClassPropertyValues": separate_class_property_values,
    }
    _put(params, "tag", tag)
    _put(params, "basePrefix", base_prefix)
    if domain_loqi is not None:
        params["domainLoqi"] = file_source(Path(domain_loqi))
    result = _safe_call(DOMAIN_ROUTE, "rdf-to-domain-loqi", params)
    return _text_or_bool(result, "loqi", output)


def solve_reasoning(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = False,
    export_domain: bool = False,
    reasoner_output_stream: TextIO | None = None,
    time_limit_seconds: int | None = None,
) -> ReasoningResult | None:
    params: dict[str, Any] = {
        "model": dir_source(model_dir),
        "domainLoqi": file_source(Path(domain_loqi)),
        "verbose": verbose,
        "debug": debug_enabled,
        "jsonTrace": json_trace,
        "exportDomain": export_domain,
    }
    _put(params, "tag", tag)
    _put(params, "tree", tree)
    if time_limit_seconds is not None:
        params["timeLimitSeconds"] = time_limit_seconds

    result = _safe_call(REASONER_ROUTE, "reason", params)
    if not isinstance(result, dict):
        return None
    return _to_reasoning_result(result, reasoner_output_stream)


def solve_reasoning_result(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    reasoner_output_stream: TextIO | None = None,
    time_limit_seconds: int | None = None,
) -> bool | None:
    result = solve_reasoning(
        model_dir,
        domain_loqi,
        tag=tag,
        tree=tree,
        verbose=verbose,
        reasoner_output_stream=reasoner_output_stream,
        time_limit_seconds=time_limit_seconds,
    )
    if not isinstance(result, ReasoningResult):
        return None
    return result.result


def query_expression(
    domain_loqi: str | Path,
    expression: str,
    *,
    model_dir: str | Path | None = None,
    tag: str | None = None,
    debug_enabled: bool = False,
    trace: bool = False,
    verbose: bool = False,
    json_trace: bool = False,
    limit: int | None = None,
    time_measure: bool = False,
    reasoner_output_stream: TextIO | None = None,
) -> ExpressionQueryResult | None:
    params: dict[str, Any] = {
        "domainLoqi": file_source(Path(domain_loqi)),
        "query": expression,
        "debug": debug_enabled,
        "trace": trace,
        "verbose": verbose,
        "jsonTrace": json_trace,
        "timeMeasure": time_measure,
    }
    if model_dir is not None:
        params["model"] = dir_source(model_dir)
    _put(params, "tag", tag)
    if limit is not None:
        params["limit"] = limit

    result = _safe_call(REASONER_ROUTE, "expression-query", params)
    if not isinstance(result, dict):
        return None
    return _to_query_result(result)


# -- mapping helpers ----------------------------------------------------------------------------


def _to_reasoning_result(result: dict[str, Any], stream: TextIO | None) -> ReasoningResult:
    exceptions_block = result.get("exceptions") or {}
    items = exceptions_block.get("items") if isinstance(exceptions_block, dict) else None
    exceptions = [
        _parse_reasoning_exception(item)
        for item in (items or [])
        if isinstance(item, dict)
    ]
    variables = {
        str(key): str(value)
        for key, value in (result.get("variables") or {}).items()
    }
    artifacts: dict[str, Any] = {}
    specific_domain = result.get("specificDomain")
    if isinstance(specific_domain, dict) and specific_domain.get("value") is not None:
        artifacts["specificDomain"] = specific_domain["value"]

    reasoner_output: list[str] = []
    for message in result.get("reasonerOutput") or []:
        text = str(message)
        reasoner_output.append(text)
        if stream:
            print(text, file=stream)

    return ReasoningResult(
        result=_parse_reasoning_result_value(result.get("branchResult")),
        trace=_as_trace(result.get("trace")),
        variables=variables,
        exceptions=exceptions,
        reasoner_output=reasoner_output,
        metrics=_as_metrics(result.get("metrics")),
        artifacts=artifacts,
    )


def _to_query_result(result: dict[str, Any]) -> ExpressionQueryResult:
    objects = [str(item) for item in (result.get("objects") or [])]
    return ExpressionQueryResult(
        objects=objects,
        trace=_as_trace(result.get("trace")),
        metrics=_as_metrics(result.get("metrics")),
    )


def _as_trace(value: Any) -> str | dict[str, Any] | list[Any] | None:
    return value if isinstance(value, str | dict | list) else None


def _as_metrics(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {str(name): metric for name, metric in value.items() if isinstance(metric, dict)}


def _build_method(build_method: DomainBuildMethod) -> str:
    return "DICT_RDF" if build_method == "RDF" else "LOQI"


# -- call plumbing ------------------------------------------------------------------------------


def _safe_call(route: str, method: str, params: dict[str, Any]) -> Any | None:
    try:
        return _rpc_call(route, method, params)
    except RpcError as exc:
        logger.error("tpg_domain %s via JSON-RPC failed: %s", method, exc)
        if exc.data:
            logger.debug("Error data: %s", exc.data)
        return None


def _put(params: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        params[key] = value


def _text_or_bool(result: Any | None, key: str, output: str | Path | None) -> str | bool | None:
    if output is not None:
        if result is None:
            return False
        text = _extract(result, key)
        if text is None:
            return False
        Path(output).write_text(text, encoding="utf-8")
        return True
    if not isinstance(result, dict):
        return None
    return _extract(result, key)


def _extract(result: Any, key: str) -> str | None:
    if not isinstance(result, dict):
        return None
    value = result.get(key)
    return None if value is None else str(value)
