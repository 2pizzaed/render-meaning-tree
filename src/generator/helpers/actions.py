from __future__ import annotations

from dataclasses import dataclass

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
)
from src.model.rules import TransitionDeclaration
from src.model.situation import Action, TraceAct


@dataclass(frozen=True, slots=True)
class ActionLinePosition:
    line_number: int
    action_index: int
    ast_id: int


def line_actions(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    include_transparent: bool = False,
) -> list[Action]:
    """Вернуть actions для строки; по умолчанию только opaque, опционально и transparent."""
    registry = _registry_for(context)
    actions: list[Action] = []
    seen: set[int] = set()
    for node in _code_manager_for(context).line_number_to_ast_nodes(line_number):
        for action in registry.get_actions_for(node.id):
            if not include_transparent and not action.is_opaque:
                continue
            action_identity = id(action)
            if action_identity in seen:
                continue
            seen.add(action_identity)
            actions.append(action)
    return actions


def require_line_action(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    action_index: int = 0,
    include_transparent: bool = False,
) -> Action:
    """Выбрать action по номеру строки и индексу действия на этой строке."""
    actions = line_actions(
        context,
        line_number,
        include_transparent=include_transparent,
    )
    if action_index < 0 or action_index >= len(actions):
        raise LookupError(
            f"Expected action index {action_index} on line {line_number}, found {len(actions)} action(s)"
        )
    return actions[action_index]


def action_line_position(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    action: Action,
    *,
    include_transparent: bool = False,
) -> ActionLinePosition | None:
    """Вернуть line/action-index/ast_id для action в терминах line_actions()."""
    if action.ast_id is None:
        return None

    code_manager = _code_manager_for(context)
    line_number = code_manager.code_line_number_by_id(action.ast_id)
    if line_number is None:
        return None

    for action_index, candidate in enumerate(
        line_actions(
            context,
            line_number,
            include_transparent=include_transparent,
        )
    ):
        if candidate is action:
            return ActionLinePosition(
                line_number=line_number,
                action_index=action_index,
                ast_id=action.ast_id,
            )
    return None


def add_trace_act_for_line(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    action_index: int = 0,
    include_transparent: bool = False,
    transition: TransitionDeclaration | None = None,
    variable_name: str | None = "P",
) -> TraceAct:
    """Создать TraceAct для action на строке и добавить его в registry."""
    registry = _registry_for(context)
    action = require_line_action(
        context,
        line_number,
        action_index=action_index,
        include_transparent=include_transparent,
    )
    trace_act = TraceAct(
        action=action,
        used_transition=_resolve_transition(action, transition),
        situation=registry.owner,
    )
    registry.add(trace_act)
    if variable_name is not None:
        registry.variables[variable_name] = trace_act
    return trace_act


def add_trace_act_for_action(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    action: Action,
    *,
    transition: TransitionDeclaration | None = None,
    variable_name: str | None = "P",
) -> TraceAct:
    """Создать TraceAct для уже выбранного action и добавить его в registry."""
    registry = _registry_for(context)
    trace_act = TraceAct(
        action=action,
        used_transition=_resolve_transition(action, transition),
        situation=registry.owner,
    )
    registry.add(trace_act)
    if variable_name is not None:
        registry.variables[variable_name] = trace_act
    return trace_act


def _registry_for(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
) -> SituationDomainDataRegistry:
    if isinstance(context, DomainDataGeneratorPipeline):
        return context.registry
    return context


def _code_manager_for(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
):
    if isinstance(context, DomainDataGeneratorPipeline):
        return context.code
    return context.owner.code


def _resolve_transition(
    action: Action,
    transition: TransitionDeclaration | None,
) -> TransitionDeclaration | None:
    if transition is not None:
        return transition
    transitions = action.possible_transitions()
    if len(transitions) == 1:
        return transitions[0]
    if not transitions:
        return None
    raise LookupError(
        f"Expected explicit transition for action {action.rule.role!r}, found {len(transitions)} candidates"
    )
