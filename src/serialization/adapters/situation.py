from __future__ import annotations

from typing import Any

from src.model.rules import (
    ActionDeclaration,
    CallStackAction,
    ConstructDeclaration,
    TransitionDeclaration,
)
from src.model.situation import Action, Construct, SemanticValue, TraceAct, TraceState
from src.serialization.loqi import (
    LoqiAdapter,
    LoqiAdapterContext,
    LoqiObjectRef,
    LoqiObjectSpec,
    RelationshipLink,
    _normalize_object_name,
)


class ConstructAdapter:
    def object_name(self, obj: Construct) -> str:
        return f"construct_{obj.rule.name}_ast{obj.ast_id}"

    def type_name(self, obj: Construct) -> str:
        return "ConcreteConstruct"

    def describe(self, obj: Construct, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        current_object = ctx.require_current_object()
        action_refs = [
            ctx.serialize(action, backlink=("belongsTo", current_object))
            for action in obj.actions
        ]

        relationships: list[RelationshipLink] = [
            *ctx.relationship_links("hasActions", action_refs),
            ctx.relationship("derivedFrom", _serialize_construct_spec(obj.rule, ctx)),
        ]
        if obj.parent is not None:
            relationships.append(ctx.relationship("hasParent", obj.parent))

        return LoqiObjectSpec(
            properties=(
                ctx.property("ast_id", obj.ast_id),
                ctx.property("ast_type", _ast_type(obj)),
            ),
            relationship_links=tuple(relationships),
        )


class ActionAdapter:
    def object_name(self, obj: Action) -> str:
        return f"{obj.parent.rule.name}__action_{obj.rule.role}_ast{obj.ast_id}"

    def type_name(self, obj: Action) -> str:
        return "ConcreteAction"

    def describe(self, obj: Action, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        consumed_count = _consumed_value_count_for_action(obj)
        obj.bind_values()
        for index, value in enumerate(obj.values):
            value.used = index < consumed_count
        value_head = obj.values[0] if obj.values else None
        relationships: list[RelationshipLink] = [
            ctx.relationship("belongsTo", obj.parent),
            ctx.relationship("derivedFrom", _serialize_action_spec(obj.rule, ctx)),
        ]
        if value_head is not None:
            relationships.append(ctx.relationship("hasValue", value_head))
        if obj.effects is not None:
            relationships.append(ctx.relationship("hasEffects", obj.effects))

        next_action = _next_by_identity(obj.chain, obj)
        if next_action is not None:
            relationships.append(ctx.relationship("directlyBeforeOf", next_action))

        return LoqiObjectSpec(
            properties=(
                ctx.property("ast_id", obj.ast_id if obj.ast_id is not None else -1),
                ctx.property("ast_type", _ast_type(obj)),
            ),
            relationship_links=tuple(relationships),
        )


class TraceActAdapter:
    def object_name(self, obj: TraceAct) -> str:
        if obj.chain_order == 0:
            return "act_root"
        return f"act_{obj.action.parent.rule.name}_{obj.action.rule.role}_{obj.chain_order}_ast{obj.action.ast_id}"

    def type_name(self, obj: TraceAct) -> str:
        return "TraceAct"

    def describe(self, obj: TraceAct, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        action_ref = ctx.serialize(obj.action)
        relationships: list[RelationshipLink] = [
            RelationshipLink(name="hasAction", targets=(action_ref,)),
        ]
        value_ref = _semantic_value_ref_for_trace_act(obj)
        if value_ref is not None:
            relationships.append(ctx.relationship("hasValue", value_ref))

        if obj.unfolded_from is not None:
            relationships.append(
                ctx.relationship("unfoldedFrom", ctx.serialize(obj.unfolded_from))
            )

        frame_act = _frame_act_for(obj)
        if frame_act is not None:
            relationships.append(ctx.relationship("inFrame", frame_act))

        if obj.used_transition is not None:
            relationships.append(
                ctx.relationship(
                    "hasTransition",
                    _serialize_transition_spec(
                        obj.used_transition,
                        obj.action.parent.rule,
                        ctx,
                        action_rule=obj.action.rule,
                    ),
                )
            )

        next_trace_act = _next_by_identity(obj.chain, obj)
        if next_trace_act is not None:
            relationships.append(ctx.relationship("directlyBeforeOf", next_trace_act))

        return LoqiObjectSpec(relationship_links=tuple(relationships))


class TraceStateAdapter:
    def object_name(self, obj: TraceState) -> str:
        return "trace_state"

    def type_name(self, obj: TraceState) -> str:
        return "TraceState"

    def describe(self, obj: TraceState, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        return LoqiObjectSpec(
            properties=(ctx.property("interruption_mode", obj.interruption_mode),)
        )


class SemanticValueAdapter:
    def object_name(self, obj: SemanticValue) -> str:
        if obj.owner is None:
            raise ValueError("SemanticValue must belong to an Action")
        return f"semantic_value_{_semantic_scope(obj.owner)}_{obj.index}"

    def type_name(self, obj: SemanticValue) -> str:
        return "SemanticValue"

    def describe(self, obj: SemanticValue, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        relationships: list[RelationshipLink] = []
        next_value = _next_by_identity(obj.chain, obj)
        if next_value is not None:
            relationships.append(ctx.relationship("directlyBeforeOf", next_value))

        return LoqiObjectSpec(
            properties=(
                ctx.property("bool_value", obj.bool_value),
                ctx.property("used", obj.used),
            ),
            relationship_links=tuple(relationships),
            metadata=ctx.object_metadata({"hint": obj.hint}),
        )


def build_situation_loqi_adapters() -> dict[type[Any], LoqiAdapter[Any]]:
    return {
        Construct: ConstructAdapter(),
        Action: ActionAdapter(),
        TraceAct: TraceActAdapter(),
        TraceState: TraceStateAdapter(),
        SemanticValue: SemanticValueAdapter(),
    }


def _semantic_value_ref_for_action(action: Action, index: int) -> LoqiObjectRef | None:
    if not action.values:
        return None
    if index < 0 or index >= len(action.values):
        return None
    return LoqiObjectRef(
        _normalize_object_name(f"semantic_value_{_semantic_scope(action)}_{index}")
    )


def _semantic_value_ref_for_trace_act(trace_act: TraceAct) -> LoqiObjectRef | None:
    if not trace_act.action.values:
        return None
    if isinstance(trace_act.value, SemanticValue):
        return _semantic_value_ref_for_action(trace_act.action, trace_act.value.index)
    return _semantic_value_ref_for_action(
        trace_act.action,
        _trace_act_value_occurrence_index(trace_act),
    )


def _frame_acts(trace_acts: list[TraceAct]) -> list[TraceAct]:
    """Кадр вызова каждого акта трассы (связь ``inFrame``).

    Кадр - акт действия func, по переходу в которое (с ``add_frame``) вошли в тело
    функции; у глобального кода - корневой акт трассы. BEGIN-акт сразу после такого
    акта открывает новый кадр, END того же конструкта его закрывает. Зеркало lambda
    ``frameAfter`` и связей ``inFrame`` в ``domain/findCorrect.tpg``.
    """
    if not trace_acts:
        return []

    stack: list[tuple[TraceAct, Construct | None]] = [(trace_acts[0], None)]
    frames: list[TraceAct] = []
    for order, trace_act in enumerate(trace_acts):
        role = trace_act.action.rule.role
        if order > 0 and role == "BEGIN" and _enters_call_frame(trace_acts[order - 1]):
            stack.append((trace_acts[order - 1], trace_act.action.parent))
        frames.append(stack[-1][0])
        if len(stack) > 1 and role == "END" and trace_act.action.parent is stack[-1][1]:
            stack.pop()
    return frames


def _enters_call_frame(trace_act: TraceAct) -> bool:
    transition = trace_act.used_transition
    if transition is None:
        return False
    transition = (
        _matching_compiled_transition(
            transition, trace_act.action.parent.rule, trace_act.action.rule
        )
        or transition
    )
    return (
        transition.effects is not None
        and transition.effects.call_stack is CallStackAction.ADD_FRAME
    )


def _frame_act_for(trace_act: TraceAct) -> TraceAct | None:
    chain = trace_act.chain
    order = trace_act.chain_order
    if order >= len(chain):
        return None
    return _frame_acts(chain)[order]


def _trace_act_value_occurrence_index(trace_act: TraceAct) -> int:
    chain = trace_act.chain
    order = trace_act.chain_order
    return sum(
        1
        for prior_trace_act in chain[:order]
        if prior_trace_act.action is trace_act.action
    )


def _consumed_value_count_for_action(action: Action) -> int:
    current_trace_act = _current_trace_act(action)
    trace_acts = action.owner.trace_acts
    explicit_indexes = [
        trace_act.value.index
        for trace_act in trace_acts
        if trace_act is not current_trace_act
        and trace_act.action is action
        and isinstance(trace_act.value, SemanticValue)
    ]
    inferred_count = sum(
        1
        for trace_act in trace_acts
        if trace_act is not current_trace_act
        and trace_act.action is action
        and trace_act.value is None
    )
    explicit_count = max(explicit_indexes, default=-1) + 1
    return max(explicit_count, inferred_count)


def _current_trace_act(action: Action) -> TraceAct | None:
    registry = getattr(action.owner, "registry", None)
    variables = getattr(registry, "variables", None) or getattr(
        action.owner, "variables", None
    )
    if not isinstance(variables, dict):
        return None
    current = variables.get("P")
    return current if isinstance(current, TraceAct) else None


def _serialize_construct_spec(
    rule: ConstructDeclaration,
    ctx: LoqiAdapterContext,
) -> LoqiObjectRef:
    return ctx.serialize(rule)


def _serialize_action_spec(
    rule: ActionDeclaration,
    ctx: LoqiAdapterContext,
) -> LoqiObjectRef:
    if rule.parent is not None:
        _serialize_construct_spec(rule.parent, ctx)
    return ctx.serialize(rule)


def _serialize_transition_spec(
    transition: TransitionDeclaration,
    construct_rule: ConstructDeclaration,
    ctx: LoqiAdapterContext,
    *,
    action_rule: ActionDeclaration | None = None,
) -> LoqiObjectRef:
    action_refs_by_role = {
        action.role: _serialize_action_spec(action, ctx)
        for action in construct_rule.actions
    }
    _serialize_construct_spec(construct_rule, ctx)
    transition = (
        _matching_compiled_transition(transition, construct_rule, action_rule)
        or transition
    )
    existing_ref = _existing_transition_ref(transition, ctx)
    if existing_ref is not None:
        return existing_ref
    return ctx.serialize(
        transition,
        state_updates={"action_refs_by_role": action_refs_by_role},
    )


def _matching_compiled_transition(
    transition: TransitionDeclaration,
    construct_rule: ConstructDeclaration,
    action_rule: ActionDeclaration | None,
) -> TransitionDeclaration | None:
    expected_from_role = (
        action_rule.role if action_rule is not None else transition.from_role
    )
    for compiled in construct_rule.compiled_transitions():
        if compiled.from_role != expected_from_role:
            continue
        if compiled.to_role != transition.to_role:
            continue
        if compiled.to_when_absent != transition.to_when_absent:
            continue
        if compiled.constraints != transition.constraints:
            continue
        return compiled
    return None


def _existing_transition_ref(
    transition: TransitionDeclaration,
    ctx: LoqiAdapterContext,
) -> LoqiObjectRef | None:
    if transition.parent is None:
        object_id = _normalize_object_name(
            f"transition_{transition.from_role}_to_{transition.to_role}"
        )
    else:
        object_id = _normalize_object_name(
            f"transition_{transition.parent.name}_{transition.from_role}_to_{transition.to_role}"
        )
    if object_id in ctx.serializer._objects_by_id:
        return LoqiObjectRef(object_id)
    return None


def _next_by_identity[T](chain: list[T], item: T) -> T | None:
    for index, existing in enumerate(chain):
        if existing is item:
            next_index = index + 1
            if next_index < len(chain):
                return chain[next_index]
            return None
    return None


def _ast_type(obj: Action | Construct) -> str:
    if isinstance(obj, Action) and obj.ast_type is not None:
        return obj.ast_type
    node = obj.ast_node
    ast_type = node.get("type") if node else None
    return ast_type if isinstance(ast_type, str) else ""


def _semantic_scope(owner: Any) -> str:
    if isinstance(owner, Action):
        return f"action_{owner.ast_id}_{owner.rule.role}"
    return f"owner_{id(owner)}"
