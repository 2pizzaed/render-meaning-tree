from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.model.situation import Action, TraceAct


@dataclass(frozen=True, slots=True)
class UiTraceButton:
    action_id: str
    node_id: int | None
    node_type: str | None
    button_type: str | None
    position: str | None
    line_index: int | None = None
    column_index: int | None = None

    @classmethod
    def from_payload(cls, raw_step: Any) -> UiTraceButton:
        action_id, payload = _read_trace_step(raw_step)
        return cls(
            action_id=action_id,
            node_id=_int_or_none(_value(payload, "nodeId", "node_id")),
            node_type=_str_or_none(_value(payload, "nodeType", "node_type")),
            button_type=_str_or_none(_value(payload, "buttonType", "button_type", "type")),
            position=_str_or_none(_value(payload, "position")),
            line_index=_int_or_none(_value(payload, "lineIndex", "line_index")),
            column_index=_int_or_none(_value(payload, "columnIndex", "column_index")),
        )

    def find_action(self, pipeline: DomainDataGeneratorPipeline) -> Action | None:
        if self.node_id is None:
            return None
        actions = pipeline.get_actions_for(self.node_id)
        if not actions:
            return None

        role = self._preferred_role()
        if role is not None:
            for action in actions:
                if action.rule.role == role:
                    return action

        for action in actions:
            if action.rule.role not in {"BEGIN", "END"}:
                return action
        return actions[0]

    def _preferred_role(self) -> str | None:
        if self.button_type == "stop":
            return "END"
        if self.button_type == "play" and self.position == "after":
            return "BEGIN"
        return None


def apply_ui_trace_buttons(
    pipeline: DomainDataGeneratorPipeline,
    selected_trace: list[Any],
) -> list[UiTraceButton]:
    registry = pipeline.registry
    registry.trace_acts = registry.trace_acts[:1]

    buttons = [UiTraceButton.from_payload(step) for step in selected_trace]
    for button in buttons:
        action = button.find_action(pipeline)
        if action is None:
            continue
        trace_act = TraceAct(
            action=action,
            used_transition=_default_transition(action),
            situation=pipeline,
        )
        registry.add(trace_act)
        registry.variables["P"] = trace_act

    if registry.trace_acts and "P" not in registry.variables:
        registry.variables["P"] = registry.trace_acts[-1]
    return buttons


def _read_trace_step(raw_step: Any) -> tuple[str, Any]:
    if isinstance(raw_step, list | tuple) and len(raw_step) >= 2:
        return str(raw_step[0]), raw_step[1]
    if isinstance(raw_step, dict):
        action_id = raw_step.get("actionId", raw_step.get("action_id", ""))
        return str(action_id), raw_step.get("value", raw_step)
    return "", raw_step


def _value(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _default_transition(action: Action):
    transitions = action.possible_transitions()
    return transitions[0] if len(transitions) == 1 else None
