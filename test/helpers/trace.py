from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
)
from src.generator.utilities import registry_to_loqi
from src.model.rules import InterruptionType, TransitionDeclaration
from src.model.situation import Action, SemanticValue, TraceAct, TraceState
from test.helpers.actions import _registry_for

_TRACE_ACT_OBJECT_RE = re.compile(
    r"(?:var\s+(?P<var_name>\w+)\s*=\s*)?obj\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*TraceAct\s*\{(?P<body>.*?)\}",
    re.DOTALL,
)
_TRACE_ACT_REF_RE = re.compile(
    r"\b(?P<rel>hasAction|hasTransition|hasValue|directlyBeforeOf)\((?P<target>[A-Za-z_][A-Za-z0-9_]*)\)\s*;"
)
_TRACE_STATE_OBJECT_RE = re.compile(
    r"(?:var\s+(?P<var_name>\w+)\s*=\s*)?obj\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*TraceState\s*\{(?P<body>.*?)\}",
    re.DOTALL,
)
_TRACE_STATE_MODE_RE = re.compile(
    r"\binterruption_mode\s*=\s*InterruptionType:(?P<mode>[A-Za-z_][A-Za-z0-9_]*)\s*;"
)
_TRACE_STATE_VAR_REF_RE = re.compile(
    r"\bvar\s+S\s*=\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;",
)


@dataclass(frozen=True, slots=True)
class _TraceActSpec:
    object_name: str
    action_name: str
    transition_name: str | None
    value_name: str | None
    next_name: str | None
    source_order: int
    variable_name: str | None = None


@dataclass(frozen=True, slots=True)
class _TraceStateSpec:
    object_name: str
    interruption_mode: InterruptionType
    variable_name: str | None


def trace_acts_from_loqi(
    loqi_text: str,
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    *,
    replace_existing: bool = True,
) -> list[TraceAct]:
    """Восстановить TraceAct из LOQI-текста и привязать их к текущему registry."""
    registry = _registry_for(context)
    serializer, _ = registry_to_loqi(registry)
    trace_specs = _parse_trace_act_specs(loqi_text)

    if replace_existing:
        registry.trace_acts.clear()

    trace_acts: list[TraceAct] = []
    for trace_spec in _order_trace_act_specs(trace_specs):
        action = serializer.object_by_name(trace_spec.action_name)
        if not isinstance(action, Action):
            raise LookupError(
                f"Expected Action for {trace_spec.action_name!r}, found {type(action).__name__}"
            )

        used_transition = None
        if trace_spec.transition_name is not None:
            used_transition = serializer.object_by_name(trace_spec.transition_name)
            if not isinstance(used_transition, TransitionDeclaration):
                raise LookupError(
                    "Expected TransitionDeclaration for "
                    f"{trace_spec.transition_name!r}, found {type(used_transition).__name__}"
                )

        value = None
        if trace_spec.value_name is not None:
            value = serializer.object_by_name(trace_spec.value_name)
            if not isinstance(value, SemanticValue):
                raise LookupError(
                    "Expected SemanticValue for "
                    f"{trace_spec.value_name!r}, found {type(value).__name__}"
                )

        trace_act = TraceAct(
            action=action,
            used_transition=used_transition,
            situation=registry.owner,
            value=value,
        )
        registry.add(trace_act)
        trace_acts.append(trace_act)

    if trace_acts:
        registry.variables["P"] = trace_acts[-1]

    return trace_acts


def trace_state_from_loqi(
    loqi_text: str,
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
) -> TraceState | None:
    """Восстановить TraceState из LOQI-текста и заменить registry.trace_state."""
    registry = _registry_for(context)
    trace_state_spec = _parse_trace_state_spec(loqi_text)
    if trace_state_spec is None:
        return None

    trace_state = TraceState(interruption_mode=trace_state_spec.interruption_mode)
    registry.add(trace_state)
    return trace_state


def restore_trace_from_loqi(
    loqi_text: str,
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    *,
    replace_existing: bool = True,
) -> tuple[list[TraceAct], TraceState | None]:
    """Восстановить TraceState и цепочку TraceAct из LOQI-текста."""
    trace_state = trace_state_from_loqi(loqi_text, context)
    trace_acts = trace_acts_from_loqi(
        loqi_text,
        context,
        replace_existing=replace_existing,
    )
    return trace_acts, trace_state


def _parse_trace_act_specs(loqi_text: str) -> list[_TraceActSpec]:
    trace_specs: list[_TraceActSpec] = []
    for index, match in enumerate(_TRACE_ACT_OBJECT_RE.finditer(loqi_text)):
        refs = {
            ref_match.group("rel"): ref_match.group("target")
            for ref_match in _TRACE_ACT_REF_RE.finditer(match.group("body"))
        }
        action_name = refs.get("hasAction")
        if action_name is None:
            raise ValueError(
                f"TraceAct {match.group('name')!r} does not declare hasAction(...)"
            )
        trace_specs.append(
            _TraceActSpec(
                object_name=match.group("name"),
                action_name=action_name,
                transition_name=refs.get("hasTransition"),
                value_name=refs.get("hasValue"),
                next_name=refs.get("directlyBeforeOf"),
                source_order=index,
                variable_name=match.group("var_name"),
            )
        )
    return trace_specs


def _parse_trace_state_spec(loqi_text: str) -> _TraceStateSpec | None:
    specs: list[_TraceStateSpec] = []
    for match in _TRACE_STATE_OBJECT_RE.finditer(loqi_text):
        mode_match = _TRACE_STATE_MODE_RE.search(match.group("body"))
        if mode_match is None:
            raise ValueError(
                f"TraceState {match.group('name')!r} does not declare interruption_mode"
            )
        specs.append(
            _TraceStateSpec(
                object_name=match.group("name"),
                interruption_mode=InterruptionType(mode_match.group("mode")),
                variable_name=match.group("var_name"),
            )
        )

    if not specs:
        return None

    direct_variable_match = next(
        (trace_state for trace_state in specs if trace_state.variable_name == "S"),
        None,
    )
    if direct_variable_match is not None:
        return direct_variable_match

    variable_ref_match = _TRACE_STATE_VAR_REF_RE.search(loqi_text)
    if variable_ref_match is not None:
        object_name = variable_ref_match.group("name")
        for trace_state in specs:
            if trace_state.object_name == object_name:
                return trace_state
        raise LookupError(f"Variable 'S' references unknown TraceState {object_name!r}")

    if len(specs) == 1:
        return specs[0]

    raise LookupError("Expected a single TraceState or an explicit variable 'S'")


def _order_trace_act_specs(trace_specs: Sequence[_TraceActSpec]) -> list[_TraceActSpec]:
    specs_by_name = {trace_spec.object_name: trace_spec for trace_spec in trace_specs}
    incoming_names = {
        trace_spec.next_name
        for trace_spec in trace_specs
        if trace_spec.next_name in specs_by_name
    }
    ordered: list[_TraceActSpec] = []
    seen: set[str] = set()

    for trace_spec in trace_specs:
        if trace_spec.object_name in incoming_names:
            continue
        _append_trace_chain(trace_spec, specs_by_name, seen, ordered)

    for trace_spec in trace_specs:
        _append_trace_chain(trace_spec, specs_by_name, seen, ordered)

    return ordered


def _append_trace_chain(
    start: _TraceActSpec,
    specs_by_name: dict[str, _TraceActSpec],
    seen: set[str],
    ordered: list[_TraceActSpec],
) -> None:
    current: _TraceActSpec | None = start
    while current is not None and current.object_name not in seen:
        ordered.append(current)
        seen.add(current.object_name)
        current = (
            specs_by_name.get(current.next_name)
            if current.next_name is not None
            else None
        )
