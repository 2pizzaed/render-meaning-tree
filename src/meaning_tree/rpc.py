"""JSON-RPC backend for meaning_tree, mirroring :mod:`src.meaning_tree.cli`.

Public functions have identical signatures to the CLI backend, but call the CompPrehension Toolchain
Server (route ``/rpc/meaning-tree``) instead of spawning the JAR. Pure parsing helpers are reused
from :mod:`src.meaning_tree.cli`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from src.toolchain_rpc import RpcError
from src.toolchain_rpc import call as _rpc_call
from src.types import (
    JSON,
    MeaningTree,
    SourceMap,
    SupportedProgrammingLanguage,
    TokenList,
)

from .cli import (
    DeserializationFormat,
    SerializationFormat,
    _normalize_deserialization_input,
    _parse_json,
    _parse_source_map,
)

ROUTE = "/rpc/meaning-tree"
logger = logging.getLogger(__name__)

DESERIALIZE_FORMATS: frozenset[str] = frozenset(DeserializationFormat.__value__.__args__)


def to_dict(
    language: SupportedProgrammingLanguage,
    code: str,
    config: JSON | None = None,
    *,
    skip_errors: bool = False,
    project_root: str | Path | None = None,
    project_file: str | Path | None = None,
) -> MeaningTree | None:
    output = _serialize(
        code, language, "json",
        config=config, skip_errors=skip_errors,
        project_root=project_root, project_file=project_file,
    )
    if not output:
        return None
    return _parse_json(output)  # type: ignore


def to_dot(
    language: SupportedProgrammingLanguage | DeserializationFormat,
    code: str,
    config: JSON | None = None,
    *,
    skip_errors: bool = False,
    project_root: str | Path | None = None,
    project_file: str | Path | None = None,
) -> str | None:
    return _serialize(
        code, language, "dot",
        config=config, skip_errors=skip_errors,
        project_root=project_root, project_file=project_file,
    )


def to_tokens(
    from_language: SupportedProgrammingLanguage,
    code: str,
    to_language: SupportedProgrammingLanguage | None = None,
    config: JSON | None = None,
    *,
    skip_errors: bool = False,
    project_root: str | Path | None = None,
    project_file: str | Path | None = None,
) -> TokenList | None:
    params: dict[str, Any] = {"from": from_language, "code": code}
    if to_language is None:
        params["tokenizeNoConvert"] = True
    else:
        params["to"] = to_language
        params["tokenize"] = True
    _add_common(params, config=config, skip_errors=skip_errors, project_root=project_root, project_file=project_file)

    output = _result_string(_call("translate", params))
    if output is None:
        return None
    return _parse_json(output)  # type: ignore


def convert(
    code: str,
    from_language: SupportedProgrammingLanguage,
    to_language: SupportedProgrammingLanguage,
    source_map: bool = False,
    config: JSON | None = None,
    *,
    skip_errors: bool = False,
    project_root: str | Path | None = None,
    project_file: str | Path | None = None,
) -> str | SourceMap | None:
    params: dict[str, Any] = {"from": from_language, "to": to_language, "code": code}
    if source_map:
        params["sourceMap"] = True
    _add_common(params, config=config, skip_errors=skip_errors, project_root=project_root, project_file=project_file)

    output = _result_string(_call("translate", params))
    if output is None:
        return None
    return _parse_source_map(output) if source_map else output


def generate(
    ast: str,
    to: SupportedProgrammingLanguage,
    format: SerializationFormat = "json",
    source_map: bool = False,
    config: JSON | None = None,
    *,
    skip_errors: bool = False,
) -> str | SourceMap | None:
    params: dict[str, Any] = {"input": ast, "format": format, "to": to}
    if source_map:
        params["sourceMap"] = True
    _add_common(params, config=config, skip_errors=skip_errors)

    output = _result_string(_call("generate", params))
    if output is None:
        return None
    return _parse_source_map(output) if source_map else output


def node_hierarchy() -> JSON:
    result = _call("node-hierarchy", {})
    if not isinstance(result, dict):
        return {}
    hierarchy = result.get("hierarchy")
    return hierarchy if isinstance(hierarchy, dict) else {}


# -- internals ----------------------------------------------------------------------------------


def _serialize(
    code: str,
    source_lang: SupportedProgrammingLanguage | DeserializationFormat,
    target: SerializationFormat,
    *,
    config: JSON | None,
    skip_errors: bool,
    project_root: str | Path | None,
    project_file: str | Path | None,
) -> str | None:
    no_translate = source_lang in DESERIALIZE_FORMATS
    if no_translate:
        normalized = _normalize_deserialization_input(cast(DeserializationFormat, source_lang), code)
        params: dict[str, Any] = {"input": normalized, "format": source_lang, "serialize": target}
        _add_common(params, config=config, skip_errors=skip_errors)
        return _result_string(_call("generate", params))

    params = {"from": source_lang, "code": code, "serialize": target}
    _add_common(params, config=config, skip_errors=skip_errors, project_root=project_root, project_file=project_file)
    return _result_string(_call("translate", params))


def _add_common(
    params: dict[str, Any],
    *,
    config: JSON | None = None,
    skip_errors: bool = False,
    project_root: str | Path | None = None,
    project_file: str | Path | None = None,
) -> None:
    if skip_errors:
        params["skipErrors"] = True
    if config:
        params["config"] = config
    project = _project(project_root, project_file)
    if project is not None:
        params["project"] = project


def _project(
    project_root: str | Path | None,
    project_file: str | Path | None,
) -> dict[str, str] | None:
    if project_root is None and project_file is None:
        return None
    if project_root is None or project_file is None:
        raise ValueError("project_root and project_file must be provided together")
    return {"root": str(Path(project_root)), "currentFile": str(Path(project_file))}


def _call(method: str, params: dict[str, Any]) -> Any | None:
    try:
        return _rpc_call(ROUTE, method, params)
    except RpcError as exc:
        logger.error("meaning_tree.%s via JSON-RPC failed: %s", method, exc)
        if exc.data:
            logger.debug("Error data: %s", exc.data)
        return None


def _result_string(result: Any | None) -> str | None:
    if not isinstance(result, dict):
        return None
    value = result.get("result")
    return None if value is None else str(value)
