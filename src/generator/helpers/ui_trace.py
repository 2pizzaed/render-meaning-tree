from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.generator.registry import SituationRegistry
from src.generator.serialization import registry_to_loqi
from src.model.situation import Action, Construct
from src.serialization.loqi import LoqiSerializer


def resolve_button_action_name(
    registry: SituationRegistry,
    button: dict[str, Any],
    *,
    serializer: LoqiSerializer | None = None,
) -> str | None:
    action = resolve_button_action(registry, button)
    if action is None:
        return None
    serializer = serializer or _serializer_for_registry(registry)
    return serializer.object_name(action)


def resolve_button_action(
    registry: SituationRegistry,
    button: dict[str, Any],
) -> Action | None:
    node_id = _int_or_none(_value(button, "node_id", "nodeId"))
    if node_id is None:
        return None

    button_type = _str_or_none(_value(button, "button_type", "buttonType", "type"))
    position = _str_or_none(_value(button, "position"))
    parent_ast_id = _parent_ast_id(registry, node_id)
    candidates = _candidate_actions(
        registry,
        button_type,
        node_id,
        parent_ast_id,
        position,
    )
    if not candidates:
        return None

    action = _resolve_single_candidate(registry, button, candidates, parent_ast_id)
    return _resolve_inline_compound_action(registry, action)


def _serializer_for_registry(registry: SituationRegistry) -> LoqiSerializer:
    serializer, _ = registry_to_loqi(registry)
    return serializer


def _candidate_actions(
    registry: SituationRegistry,
    button_type: str | None,
    node_id: int,
    parent_ast_id: int | None,
    position: str | None,
) -> list[Action]:
    if button_type == "stop":
        return _all_actions_matching(
            registry,
            lambda action: action.rule.role == "END",
        )

    if button_type == "play":
        return _start_candidates(registry, node_id, parent_ast_id, position)

    if button_type == "step-into":
        return _call_boundary_candidates(registry, "BEGIN")

    if button_type == "step-out":
        return _call_boundary_candidates(registry, "END")

    if button_type == "question":
        return _all_actions_matching(
            registry,
            lambda action: "condition" in action.rule.kind_classes
            and not _expands_to_non_inline_construct(action),
        )

    return []


def _start_candidates(
    registry: SituationRegistry,
    node_id: int,
    parent_ast_id: int | None,
    position: str | None,
) -> list[Action]:
    if position == "after":
        return _all_actions_matching(
            registry,
            lambda action: action.rule.role == "BEGIN",
        )

    if position == "before":
        return _all_actions_matching(
            registry,
            lambda action: action.parent.ast_id == parent_ast_id
            and not _expands_to_non_inline_construct(action),
        )

    return _all_actions_matching(
        registry,
        lambda action: action.ast_id == node_id
        and not _expands_to_non_inline_construct(action),
    )


def _call_boundary_candidates(
    registry: SituationRegistry,
    role: str,
) -> list[Action]:
    return _all_actions_matching(
        registry,
        lambda action: action.rule.role == role
        and "call" in action.parent.rule.kind_classes,
    )


def _resolve_single_candidate(
    registry: SituationRegistry,
    button: dict[str, Any],
    candidates: list[Action],
    parent_ast_id: int | None,
) -> Action:
    node_id = _int_or_none(_value(button, "node_id", "nodeId"))
    candidates = _prefer(candidates, lambda action: action.ast_id == node_id)
    candidates = _prefer(candidates, lambda action: action.parent.ast_id == parent_ast_id)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise AssertionError("Candidate filtering unexpectedly removed all actions")
    raise LookupError(_ambiguous_button_action_message(registry, button, candidates))


def _resolve_inline_compound_action(
    registry: SituationRegistry,
    action: Action,
) -> Action:
    construct = action.expands_to()
    if construct is None or not {"inline", "compound"}.issubset(
        construct.rule.kind_classes
    ):
        return action

    opaque_actions = [
        candidate
        for candidate in registry.get_related_actions(construct)
        if candidate.is_opaque
    ]
    # Если внутри конструкта нет непрозрачных действий (служебное content прозрачно,
    # а вложенный вызов размечен своими BEGIN/END), шагом студента остаётся само
    # действие - оператор или условие (first_cond), на него и ссылается кнопка.
    if not opaque_actions:
        return action
    return sorted(opaque_actions, key=registry.action_order)[0]


def _all_actions_matching(
    registry: SituationRegistry,
    predicate: Callable[[Action], bool],
) -> list[Action]:
    return [
        action
        for action in (*registry.all_actions(), *registry.anonymous_actions)
        if predicate(action)
    ]


def _prefer(
    actions: list[Action],
    predicate: Callable[[Action], bool],
) -> list[Action]:
    preferred = [action for action in actions if predicate(action)]
    return preferred or actions


def _parent_ast_id(registry: SituationRegistry, node_id: int) -> int | None:
    path = registry.code.ast.get_path(node_id)
    if path is None or path.parent is None:
        return None
    return path.parent.id


def _expands_to_non_inline_construct(action: Action) -> bool:
    construct = action.expands_to()
    return construct is not None and "inline" not in construct.rule.kind_classes


def _ambiguous_button_action_message(
    registry: SituationRegistry,
    button: dict[str, Any],
    candidates: list[Action],
) -> str:
    action_id = _value(button, "action_id", "actionId")
    node_id = _value(button, "node_id", "nodeId")
    position = _str_or_none(_value(button, "position"))
    button_type = _str_or_none(_value(button, "button_type", "buttonType", "type"))
    candidate_lines = "; ".join(
        _format_action(registry, action) for action in candidates
    )
    return (
        "Ambiguous button action mapping: "
        f"action_id={action_id!r}, node_id={node_id!r}, "
        f"button_type={button_type!r}, position={position!r}, "
        f"candidates=[{candidate_lines}]"
    )


def _format_action(
    registry: SituationRegistry,
    action: Action,
) -> str:
    expands_to = action.expands_to()
    expands_to_name = expands_to.rule.name if isinstance(expands_to, Construct) else None
    return (
        f"Action(role={action.rule.role!r}, ast_id={action.ast_id!r}, "
        f"kind={action.rule.kind!r}, parent_ast_id={action.parent.ast_id!r}, "
        f"parent={action.parent.rule.name!r}, expands_to={expands_to_name!r}, "
        f"order={registry.action_order(action)})"
    )


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
