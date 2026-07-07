"""JSON-RPC backend for tpg_domain, mirroring :mod:`src.tpg_domain.cli`.

Public functions have identical signatures to the CLI backend but call the CompPrehension Toolchain
Server (routes ``/rpc/domain`` and ``/rpc/reasoner``). Directory arguments are packed into DirSource
payloads; file arguments are read and sent inline.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from src.toolchain_rpc import RpcError, dir_source, file_source
from src.toolchain_rpc import call as _rpc_call

from .models import (
    DiscoverTreeResult,
    DomainBuildMethod,
    ExpressionQueryResult,
    ReasoningResult,
    TreeNode,
    _format_human_value,
    _parse_objects_loqi,
    _parse_reasoning_exception,
    _parse_reasoning_result_value,
    _parse_tree_node,
)

DOMAIN_ROUTE = "/rpc/domain"
REASONER_ROUTE = "/rpc/reasoner"

logger = logging.getLogger(__name__)


def validate_domain_solving_model(
    model_dir: str | Path,
    build_method: DomainBuildMethod = "LOQI",
    *,
    debug_enabled: bool = False,
) -> bool:
    result = _safe_call(DOMAIN_ROUTE, "validate-dsm", {
        "model": dir_source(model_dir),
        "buildMethod": _build_method(build_method),
        "debug": debug_enabled,
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


def discover_tree(
    tree_file: str | Path,
    meta: Sequence[tuple[str, str]],
    *,
    union: bool = False,
    limit: int | None = None,
    debug_enabled: bool = False,
    children: bool = False,
) -> DiscoverTreeResult | None:
    tree_path = Path(tree_file)
    params: dict[str, Any] = {
        "meta": [{"name": name, "value": value} for name, value in meta],
        "union": union,
        "debug": debug_enabled,
        "children": children,
    }
    if tree_path.suffix.lower() == ".xml":
        params["treeXml"] = file_source(tree_path)
    else:
        params["treeLoqi"] = file_source(tree_path)
    if limit is not None:
        params["limit"] = limit

    result = _safe_call(DOMAIN_ROUTE, "discover-tree", params)
    if not isinstance(result, dict):
        return None
    return _to_discover_tree_result(result)


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
    loqi: bool = False,
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
        "loqi": loqi,
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
        final_node=_parse_tree_node(result.get("finalNode")),
        trace=_as_trace(result.get("trace")),
        variables=variables,
        exceptions=exceptions,
        reasoner_output=reasoner_output,
        metrics=_as_metrics(result.get("metrics")),
        artifacts=artifacts,
    )


def _to_discover_tree_result(result: dict[str, Any]) -> DiscoverTreeResult:
    nodes_raw = result.get("nodes")
    nodes: list[TreeNode] = []
    if isinstance(nodes_raw, list):
        nodes = [node for node in map(_parse_tree_node, nodes_raw) if node is not None]
    return DiscoverTreeResult(
        found=int(result.get("found") or 0),
        shown=int(result.get("shown") or 0),
        nodes=nodes,
    )


def _to_query_result(result: dict[str, Any]) -> ExpressionQueryResult:
    objects = [str(item) for item in (result.get("objects") or [])]
    return ExpressionQueryResult(
        objects=objects,
        objects_loqi=_parse_objects_loqi(result.get("objectsLoqi")),
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
        _log_rpc_error_data(exc.data)
        return None


def _log_rpc_error_data(data: Any) -> None:
    if not isinstance(data, dict):
        return
    exception_name = data.get("exceptionName")
    root_cause_message = data.get("rootCauseMessage")
    stack_trace = data.get("stackTrace")
    header = "Server exception"
    if exception_name:
        header += f" {exception_name}"
    if root_cause_message:
        header += f": {root_cause_message}"
    if stack_trace:
        logger.error("%s\n%s", header, stack_trace)
    elif exception_name or root_cause_message:
        logger.error("%s", header)
    _log_rpc_event_value(
        data,
        event_types={"trace", "partialTrace", "partialExpressionTrace"},
        data_keys=("trace", "partialTrace", "partialExpressionTrace"),
        label="Trace",
    )
    _log_rpc_event_value(
        data,
        event_types={"variables"},
        data_keys=("variables",),
        label="Variables",
    )


def _log_rpc_event_value(
    data: Any,
    *,
    event_types: set[str],
    data_keys: tuple[str, ...],
    label: str,
) -> None:
    value = _find_rpc_event_value(data, event_types=event_types, data_keys=data_keys)
    if value is not None:
        logger.error("%s:\n%s", label, _format_human_value(value))


def _find_rpc_event_value(
    data: Any,
    *,
    event_types: set[str],
    data_keys: tuple[str, ...],
) -> Any | None:
    if isinstance(data, dict):
        for key in data_keys:
            if key in data and data[key] is not None:
                return data[key]
        event_type = data.get("type")
        if event_type in event_types and data.get("value") is not None:
            return data.get("value")
        for nested_key in ("error", "data", "details", "payload", "events", "items", "value"):
            if nested_key in data:
                found = _find_rpc_event_value(
                    data[nested_key], event_types=event_types, data_keys=data_keys
                )
                if found is not None:
                    return found
    elif isinstance(data, list):
        for item in data:
            found = _find_rpc_event_value(item, event_types=event_types, data_keys=data_keys)
            if found is not None:
                return found
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
        Path(output).write_text(text, encoding="utf-8", newline="")
        return True
    if not isinstance(result, dict):
        return None
    return _extract(result, key)


def _extract(result: Any, key: str) -> str | None:
    if not isinstance(result, dict):
        return None
    value = result.get(key)
    return None if value is None else str(value)
