from __future__ import annotations

from typing import Any

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import registry_to_loqi
from src.model.situation import Action
from src.serialization.loqi import LoqiSerializer


def resolve_button_action_name(
    pipeline: DomainDataGeneratorPipeline,
    button: dict[str, Any],
    *,
    serializer: LoqiSerializer | None = None,
) -> str | None:
    action = resolve_button_action(pipeline, button)
    if action is None:
        return None
    serializer = serializer or _serializer_for_pipeline(pipeline)
    return serializer.object_name(action)


def resolve_button_action(
    pipeline: DomainDataGeneratorPipeline,
    button: dict[str, Any],
) -> Action | None:
    node_id = _int_or_none(_value(button, "node_id", "nodeId"))
    if node_id is None:
        return None

    actions = pipeline.get_actions_for(node_id)
    if not actions:
        return None

    preferred_role = _preferred_role(button)
    if preferred_role is not None:
        for action in actions:
            if action.rule.role == preferred_role:
                return action

    for action in actions:
        if action.rule.role not in {"BEGIN", "END"}:
            return action
    return actions[0]


def _serializer_for_pipeline(pipeline: DomainDataGeneratorPipeline) -> LoqiSerializer:
    serializer, _ = registry_to_loqi(pipeline.registry)
    return serializer


def _preferred_role(button: dict[str, Any]) -> str | None:
    button_type = _str_or_none(_value(button, "button_type", "buttonType", "type"))
    position = _str_or_none(_value(button, "position"))
    if button_type == "stop":
        return "END"
    if button_type == "play" and position == "after":
        return "BEGIN"
    return None


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
