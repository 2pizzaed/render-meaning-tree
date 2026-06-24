"""Backend-agnostic data model for tpg_domain reasoning results.

Holds the dataclasses, type aliases and the JSONL parsers shared by the CLI backend
(:mod:`src.tpg_domain.cli`) and the JSON-RPC backend (:mod:`src.tpg_domain.rpc`).
"""

from __future__ import annotations

import json
import logging
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
class ExpressionQueryResult:
    objects: list[str] = field(default_factory=list)
    trace: ReasoningTrace | None = None
    reasoner_output: list[str] = field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ReasoningResult:
    result: bool | None
    trace: ReasoningTrace | None = None
    variables: dict[str, str] = field(default_factory=dict)
    exceptions: list[ReasoningException] = field(default_factory=list)
    reasoner_output: list[str] = field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, Path] = field(default_factory=dict)

    @property
    def trace_format(self) -> Literal["none", "text", "json"]:
        if self.trace is None:
            return "none"
        if isinstance(self.trace, str):
            return "text"
        return "json"

    def __str__(self) -> str:
        lines = [f"Result: {self.result}"]

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
    trace: ReasoningTrace | None = None
    reasoner_output: list[str] = []
    variables: dict[str, str] = {}
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
        elif event_type == "variables":
            event_variables = event.get("value")
            if isinstance(event_variables, dict):
                variables = {
                    str(key): str(value) for key, value in event_variables.items()
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
        trace=trace,
        variables=variables,
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
        trace=trace,
        reasoner_output=reasoner_output,
        metrics=metrics,
    )


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


def _parse_reasoning_exception(value: dict[str, Any]) -> ReasoningException:
    return ReasoningException(
        id=None if value.get("id") is None else str(value.get("id")),
        result=_parse_reasoning_result_value(value.get("result")),
        exception_name=None
        if value.get("exceptionName") is None
        else str(value.get("exceptionName")),
    )


def _indent_human_value(value: Any) -> list[str]:
    rendered = _format_human_value(value)
    return [f"  {line}" if line else "" for line in rendered.splitlines()]


def _format_human_value(value: Any) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
