"""Backend-agnostic data model for tpg_domain reasoning results.

Holds the dataclasses, type aliases and the JSONL parsers shared by the CLI backend
(:mod:`src.tpg_domain.cli`) and the JSON-RPC backend (:mod:`src.tpg_domain.rpc`).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TextIO

type TpgProject = Literal["its_DomainModel", "its_Reasoner"]
type DomainBuildMethod = Literal["LOQI", "RDF"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReasoningException:
    id: str | None
    result: bool | None
    exception_name: str | None = None


type ReasoningTrace = str | dict[str, Any] | list[Any]


@dataclass(frozen=True)
class TreeNodeMetadataEntry:
    """One metadata entry of a decision tree node: property name, localization code
    (``None`` for unlocalized values) and the raw value."""

    name: str
    loc_code: str | None
    value: Any


@dataclass(frozen=True)
class TreeNodeDescriptor:
    """A named-node descriptor built from ``id``/``line``/``skill`` metadata (only the
    ones that are present)."""

    id: Any | None = None
    line: Any | None = None
    skill: Any | None = None


@dataclass(frozen=True)
class TreeNodeChildren:
    """Immediate (depth-1) children of a decision tree node: total count plus
    descriptors of the named ones (unnamed children are counted but not listed)."""

    total: int
    descriptors: list[TreeNodeDescriptor] = field(default_factory=list)


@dataclass(frozen=True)
class TreeNode:
    """A decision tree node's concrete type plus all its metadata (including
    localized entries and ``line``, when present). Mirrors its_DomainModel's
    ``DecisionTreeNodeView``, used both by ``discover-tree`` results and as the
    ``reason`` command's final node. ``children`` is only populated by
    ``discover-tree`` when requested."""

    node_type: str
    metadata: list[TreeNodeMetadataEntry] = field(default_factory=list)
    children: TreeNodeChildren | None = None


@dataclass(frozen=True)
class DiscoverTreeResult:
    found: int
    shown: int
    nodes: list[TreeNode] = field(default_factory=list)


@dataclass(frozen=True)
class ExpressionQueryResult:
    objects: list[str] = field(default_factory=list)
    objects_loqi: dict[str, str] = field(default_factory=dict)
    trace: ReasoningTrace | None = None
    reasoner_output: list[str] = field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ReasoningResult:
    result: bool | None
    trace: ReasoningTrace | None = None
    variables: dict[str, str] = field(default_factory=dict)
    variable_objects: dict[str, Any] = field(default_factory=dict)
    exceptions: list[ReasoningException] = field(default_factory=list)
    reasoner_output: list[str] = field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    final_node: TreeNode | None = None

    @property
    def trace_format(self) -> Literal["none", "text", "json"]:
        if self.trace is None:
            return "none"
        if isinstance(self.trace, str):
            return "text"
        return "json"

    def __str__(self) -> str:
        lines = [f"Result: {self.result}"]

        if self.final_node is not None:
            lines.append("Final node:")
            lines.extend(_format_tree_node_lines(self.final_node))

        lines.append("Exceptions:")
        if self.exceptions:
            lines.extend(
                (
                    "  - "
                    f"id={exception.id}; "
                    f"result={exception.result}; "
                    f"exceptionName={exception.exception_name}"
                )
                for exception in self.exceptions
            )
        else:
            lines.append("  <empty>")

        lines.append("Trace:")
        lines.extend(_indent_human_value(self.trace))

        lines.append("Variables:")
        if self.variables:
            for name, value in sorted(self.variables.items()):
                lines.append(f"  {name} = {value}")
        else:
            lines.append("  <empty>")

        lines.append("Metrics:")
        if self.metrics:
            for name, metric in sorted(self.metrics.items()):
                details = {
                    key: value
                    for key, value in metric.items()
                    if key not in {"type", "name"}
                }
                rendered_metric = _format_human_value(details).splitlines()
                if rendered_metric:
                    lines.append(f"  {name}: {rendered_metric[0]}")
                    lines.extend(f"    {line}" for line in rendered_metric[1:])
        else:
            lines.append("  <empty>")

        if self.artifact_paths:
            lines.append("Artifact paths:")
            for name, path in sorted(self.artifact_paths.items()):
                lines.append(f"  {name}: {path}")

        return "\n".join(lines)


def parse_reasoning_jsonl(
    raw_jsonl: str,
    *,
    reasoner_output_stream: TextIO | None = None,
) -> ReasoningResult:
    """Parse its_Reasoner JSONL events into a structured result."""
    result: bool | None = None
    final_node: TreeNode | None = None
    trace: ReasoningTrace | None = None
    reasoner_output: list[str] = []
    variables: dict[str, str] = {}
    variable_objects: dict[str, Any] = {}
    exceptions: list[ReasoningException] = []
    metrics: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, Any] = {}
    artifact_paths: dict[str, Path] = {}

    for line_number, line in enumerate(raw_jsonl.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSONL from its_Reasoner at line {line_number}: {line}"
            ) from e
        if not isinstance(event, dict):
            raise ValueError(
                f"Invalid JSONL event from its_Reasoner at line {line_number}: {event!r}"
            )

        event_type = event.get("type")

        if event_type == "reasoner-output":
            message = str(event.get("value", ""))
            reasoner_output.append(message)
            if reasoner_output_stream:
                print(message, file=reasoner_output_stream)
        elif event_type == "result":
            result = _parse_reasoning_result_value(event.get("value"))
        elif event_type == "final-node":
            final_node = _parse_tree_node(event)
        elif event_type == "variables":
            event_variables = event.get("value")
            if isinstance(event_variables, dict):
                variable_objects = {
                    str(key): value for key, value in event_variables.items()
                }
                variables = {
                    str(key): _variable_value_to_str(value)
                    for key, value in event_variables.items()
                }
        elif event_type == "exceptions":
            event_exceptions = event.get("value")
            if isinstance(event_exceptions, list):
                exceptions = [
                    _parse_reasoning_exception(exception)
                    for exception in event_exceptions
                    if isinstance(exception, dict)
                ]
        elif event_type == "trace":
            event_trace = event.get("value")
            if isinstance(event_trace, str | dict | list):
                trace = event_trace
        elif event_type == "metric":
            name = event.get("name")
            if name is not None:
                metrics[str(name)] = event
        elif event_type == "artifact":
            name = event.get("name")
            if name is not None:
                artifacts[str(name)] = event.get("value")
        elif event_type == "service" and event.get("name") == "exportDomain":
            path = event.get("path")
            if path is not None:
                artifact_paths["specificDomain"] = Path(str(path))

    return ReasoningResult(
        result=result,
        final_node=final_node,
        trace=trace,
        variables=variables,
        variable_objects=variable_objects,
        exceptions=exceptions,
        reasoner_output=reasoner_output,
        metrics=metrics,
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )


def parse_expression_query_jsonl(
    raw_jsonl: str,
    *,
    reasoner_output_stream: TextIO | None = None,
) -> ExpressionQueryResult:
    """Parse its_Reasoner expression-query JSONL events into a structured result."""
    objects: list[str] = []
    objects_loqi: dict[str, str] = {}
    trace: ReasoningTrace | None = None
    reasoner_output: list[str] = []
    metrics: dict[str, dict[str, Any]] = {}

    for line_number, line in enumerate(raw_jsonl.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSONL from its_Reasoner at line {line_number}: {line}"
            ) from e
        if not isinstance(event, dict):
            raise ValueError(
                f"Invalid JSONL event from its_Reasoner at line {line_number}: {event!r}"
            )

        event_type = event.get("type")
        if event_type == "reasoner-output":
            message = str(event.get("value", ""))
            reasoner_output.append(message)
            if reasoner_output_stream:
                print(message, file=reasoner_output_stream)
        elif event_type == "expression-query-result":
            event_objects = event.get("objects")
            if isinstance(event_objects, list):
                objects = [str(item) for item in event_objects]
            objects_loqi = _parse_objects_loqi(event.get("objectsLoqi"))
        elif event_type == "expression-trace":
            event_trace = event.get("value")
            if isinstance(event_trace, str | dict | list):
                trace = event_trace
        elif event_type == "metric":
            name = event.get("name")
            if name is not None:
                metrics[str(name)] = event

    return ExpressionQueryResult(
        objects=objects,
        objects_loqi=objects_loqi,
        trace=trace,
        reasoner_output=reasoner_output,
        metrics=metrics,
    )


def _variable_value_to_str(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("repr_name"), str):
        return value["repr_name"]
    return str(value)


def variable_localized_name(value: Any, loc_code: str) -> str:
    if not isinstance(value, dict):
        return str(value)
    localized = _metadata_localized_value(value.get("metadata"), "localizedName", loc_code)
    if localized is not None:
        return localized
    object_name = value.get("object_name")
    if object_name is not None:
        return str(object_name)
    repr_name = value.get("repr_name")
    if repr_name is not None:
        return str(repr_name)
    return str(value)


def _metadata_localized_value(metadata: Any, name: str, loc_code: str) -> str | None:
    if not isinstance(metadata, list):
        return None
    grouped: dict[str | None, list[str]] = {}
    for entry in metadata:
        if (
            isinstance(entry, dict)
            and entry.get("name") == name
            and entry.get("value") is not None
        ):
            grouped.setdefault(entry.get("locCode"), []).append(str(entry.get("value")))
    values = (
        grouped.get(loc_code)
        or grouped.get(loc_code.lower())
        or grouped.get(None)
        or [value for entries in grouped.values() for value in entries]
    )
    return values[0] if values else None


def _parse_objects_loqi(value: Any) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    return {
        str(entry["name"]): str(entry["loqi"])
        for entry in value
        if isinstance(entry, dict) and entry.get("name") is not None and entry.get("loqi") is not None
    }


def _parse_reasoning_result_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if normalized in {"true", "correct"}:
        return True
    if normalized in {"false", "error"}:
        return False
    if normalized in {"null", "none"}:
        return None
    logger.warning("Unknown its_Reasoner result value: %r", value)
    return None


def parse_discover_tree_jsonl(raw_jsonl: str) -> DiscoverTreeResult:
    """Parse its_DomainModel discover-tree JSONL events into a structured result."""
    found = 0
    shown = 0
    nodes: list[TreeNode] = []

    for event in _iter_jsonl_events(raw_jsonl, "its_DomainModel"):
        event_type = event.get("type")
        if event_type == "summary":
            found = int(event.get("found") or 0)
            shown = int(event.get("shown") or 0)
        elif event_type == "node":
            node = _parse_tree_node(event)
            if node is not None:
                nodes.append(node)

    return DiscoverTreeResult(found=found, shown=shown, nodes=nodes)


def _iter_jsonl_events(raw_jsonl: str, source: str) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from JSONL text, raising ``ValueError`` on malformed lines."""
    for line_number, line in enumerate(raw_jsonl.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSONL from {source} at line {line_number}: {line}") from e
        if not isinstance(event, dict):
            raise ValueError(f"Invalid JSONL event from {source} at line {line_number}: {event!r}")
        yield event


def _parse_tree_node(value: Any) -> TreeNode | None:
    if not isinstance(value, dict):
        return None
    node_type = value.get("nodeType")
    if node_type is None:
        return None
    metadata_raw = value.get("metadata")
    metadata = (
        [entry for entry in map(_parse_tree_node_metadata_entry, metadata_raw) if entry is not None]
        if isinstance(metadata_raw, list)
        else []
    )
    return TreeNode(
        node_type=str(node_type),
        metadata=metadata,
        children=_parse_tree_node_children(value.get("children")),
    )


def _parse_tree_node_metadata_entry(value: Any) -> TreeNodeMetadataEntry | None:
    if not isinstance(value, dict) or value.get("name") is None:
        return None
    loc_code = value.get("locCode")
    return TreeNodeMetadataEntry(
        name=str(value["name"]),
        loc_code=None if loc_code is None else str(loc_code),
        value=value.get("value"),
    )


def _parse_tree_node_children(value: Any) -> TreeNodeChildren | None:
    if not isinstance(value, dict) or value.get("total") is None:
        return None
    descriptors_raw = value.get("descriptors")
    descriptors = (
        [d for d in map(_parse_tree_node_descriptor, descriptors_raw) if d is not None]
        if isinstance(descriptors_raw, list)
        else []
    )
    return TreeNodeChildren(total=int(value["total"]), descriptors=descriptors)


def _parse_tree_node_descriptor(value: Any) -> TreeNodeDescriptor | None:
    if not isinstance(value, dict):
        return None
    return TreeNodeDescriptor(id=value.get("id"), line=value.get("line"), skill=value.get("skill"))


def _parse_reasoning_exception(value: dict[str, Any]) -> ReasoningException:
    return ReasoningException(
        id=None if value.get("id") is None else str(value.get("id")),
        result=_parse_reasoning_result_value(value.get("result")),
        exception_name=None
        if value.get("exceptionName") is None
        else str(value.get("exceptionName")),
    )


def _format_tree_node_lines(node: TreeNode) -> list[str]:
    lines = [f"  {node.node_type}"]
    for entry in node.metadata:
        label = f"{entry.name}[{entry.loc_code}]" if entry.loc_code else entry.name
        lines.append(f"    {label} = {entry.value}")
    return lines


def _indent_human_value(value: Any) -> list[str]:
    rendered = _format_human_value(value)
    return [f"  {line}" if line else "" for line in rendered.splitlines()]


def _format_human_value(value: Any) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
