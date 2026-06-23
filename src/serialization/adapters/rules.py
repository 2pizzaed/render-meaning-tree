from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.model.rules import (
    ActionDeclaration,
    Behaviour,
    CallStackAction,
    ConstraintsDeclaration,
    ConstructDeclaration,
    EffectDeclaration,
    Identification,
    InterruptionType,
    Metadata,
    TransitionDeclaration,
)
from src.serialization.loqi import (
    LoqiAdapter,
    LoqiAdapterContext,
    LoqiDomainMismatchError,
    LoqiObjectRef,
    LoqiObjectSpec,
)

OPTIONAL_BOOL_VALUES = {
    True: "`true`",
    False: "`false`",
    None: "`null`",
}


@dataclass(slots=True)
class ActionSpecChainPlaceholder:
    transition: TransitionDeclaration
    role: str
    index: int
    next: ActionSpecChainPlaceholder | None = None


class ConstructDeclarationAdapter:
    def object_name(self, obj: ConstructDeclaration) -> str:
        return f"construct_{obj.name}"

    def type_name(self, obj: ConstructDeclaration) -> str:
        return "ConstructSpec"

    def describe(self, obj: ConstructDeclaration, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        current_object = ctx.require_current_object()

        action_refs: list[LoqiObjectRef] = []
        action_refs_by_role: dict[str, LoqiObjectRef] = {}
        for action in obj.actions:
            action_ref = ctx.serialize(action, backlink=("belongsTo", current_object))
            action_refs.append(action_ref)
            action_refs_by_role[action.role] = action_ref

        transition_refs = [
            ctx.serialize(
                transition,
                backlink=("belongsTo", current_object),
                state_updates={"action_refs_by_role": action_refs_by_role},
            )
            for transition in obj.compiled_transitions()
        ]

        return LoqiObjectSpec(
            properties=(
                ctx.property("name", obj.name),
                ctx.property("kind", obj.kind),
            ),
            relationship_links=(
                *ctx.relationship_links("hasActions", action_refs),
                *ctx.relationship_links("hasTransitions", transition_refs),
            ),
            metadata=_metadata_entries(ctx, obj.metadata),
        )


class ActionDeclarationAdapter:
    def object_name(self, obj: ActionDeclaration) -> str:
        return f"action_{obj.role}"

    def type_name(self, obj: ActionDeclaration) -> str:
        return "ActionSpec"

    def describe(self, obj: ActionDeclaration, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        relationships = []
        if obj.parent is not None:
            relationships.append(ctx.relationship("belongsTo", obj.parent))

        properties = [
            ctx.property("role", obj.role),
            ctx.property("kind", obj.kind),
            ctx.property("is_opaque", obj.is_opaque)
        ]
        if obj.generalization is not None:
            properties.append(ctx.property("generalization", obj.generalization))

        return LoqiObjectSpec(
            properties=tuple(properties),
            relationship_links=tuple(relationships),
            metadata=_metadata_entries(ctx, obj.metadata),
        )


class TransitionDeclarationAdapter:
    def object_name(self, obj: TransitionDeclaration) -> str:
        return _transition_object_name(obj)

    def type_name(self, obj: TransitionDeclaration) -> str:
        return "TransitionSpec"

    def describe(self, obj: TransitionDeclaration, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        action_refs_by_role = ctx.require_state("action_refs_by_role")
        relationships = [
            ctx.relationship("from_", _resolve_action_ref(action_refs_by_role, obj.from_role)),
            ctx.relationship("to_", _resolve_action_ref(action_refs_by_role, obj.to_role)),
        ]

        if obj.to_when_absent is not None:
            absent_roles = obj.to_when_absent if isinstance(obj.to_when_absent, list) else [obj.to_when_absent]
            relationships.append(
                ctx.relationship(
                    "to_when_absent",
                    _action_spec_chain_head(obj, absent_roles),
                )
            )

        if obj.constraints is not None:
            relationships.append(ctx.relationship("hasConstraints", ctx.serialize(obj.constraints)))
        if obj.effects is not None:
            relationships.append(ctx.relationship("hasEffects", obj.effects))

        return LoqiObjectSpec(relationship_links=tuple(relationships))


class ActionSpecChainPlaceholderAdapter:
    def object_name(self, obj: ActionSpecChainPlaceholder) -> str:
        return f"{_transition_object_name(obj.transition)}_to_when_absent_{obj.index}_{obj.role}"

    def type_name(self, obj: ActionSpecChainPlaceholder) -> str:
        return "ActionSpecChainPlaceholder"

    def describe(
        self, obj: ActionSpecChainPlaceholder, ctx: LoqiAdapterContext
    ) -> LoqiObjectSpec:
        action_refs_by_role = ctx.require_state("action_refs_by_role")
        relationships = [
            ctx.relationship(
                "contains",
                _resolve_action_ref(action_refs_by_role, obj.role),
            )
        ]
        if obj.next is not None:
            relationships.append(ctx.relationship("directlyBeforeOf", obj.next))
        return LoqiObjectSpec(relationship_links=tuple(relationships))


class EffectDeclarationAdapter:
    def object_name(self, obj: EffectDeclaration) -> str:
        parts = [
            "effect",
            obj.interruption_start.value if obj.interruption_start is not None else None,
            obj.interruption_stop.value if obj.interruption_stop is not None else None,
            obj.call_stack.value if obj.call_stack is not None else None,
        ]
        return "_".join(part for part in parts if part)

    def type_name(self, obj: EffectDeclaration) -> str:
        return "Effect"

    def describe(self, obj: EffectDeclaration, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        return LoqiObjectSpec(
            properties=(
                ctx.property(
                    "interruption_start",
                    obj.interruption_start or InterruptionType.NONE,
                ),
                ctx.property(
                    "interruption_stop",
                    obj.interruption_stop or InterruptionType.NONE,
                ),
                ctx.property("call_stack", obj.call_stack or CallStackAction.NONE),
            )
        )


class ConstraintsDeclarationAdapter:
    def object_name(self, obj: ConstraintsDeclaration) -> str:
        condition_name = {True: "true", False: "false", None: "no_value"}[obj.condition_value]
        interruption_name = obj.interruption_mode.value if obj.interruption_mode is not None else "any"
        return f"constraint_{condition_name}_{interruption_name}"

    def type_name(self, obj: ConstraintsDeclaration) -> str:
        return "Constraint"

    def describe(self, obj: ConstraintsDeclaration, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        properties = []
        properties.append(
            ctx.property(
                "condition_value",
                obj.condition_value,
                enum_name="OptionalBool",
                value_map=OPTIONAL_BOOL_VALUES,
            )
        )
        properties.append(ctx.property("interruption_mode", obj.interruption_mode or InterruptionType.ANY))
        return LoqiObjectSpec(properties=tuple(properties))


class UnsupportedDomainAdapter:
    def __init__(self, type_name: str, message: str) -> None:
        self._type_name = type_name
        self._message = message

    def object_name(self, obj: Any) -> str:
        return self._type_name

    def type_name(self, obj: Any) -> str:
        return self._type_name

    def describe(self, obj: Any, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        raise LoqiDomainMismatchError(self._message)


def build_rules_loqi_adapters() -> dict[type[Any], LoqiAdapter[Any]]:
    return {
        ConstructDeclaration: ConstructDeclarationAdapter(),
        ActionDeclaration: ActionDeclarationAdapter(),
        TransitionDeclaration: TransitionDeclarationAdapter(),
        ActionSpecChainPlaceholder: ActionSpecChainPlaceholderAdapter(),
        EffectDeclaration: EffectDeclarationAdapter(),
        ConstraintsDeclaration: ConstraintsDeclarationAdapter(),
        Behaviour: UnsupportedDomainAdapter(
            "Behaviour",
            "Behaviour is referenced by ActionSpec.hasBehaviour but class Behaviour is missing in domain/domain.loqi",
        ),
        Metadata: UnsupportedDomainAdapter(
            "Metadata",
            "Metadata must be attached as object metadata, not serialized as a standalone object",
        ),
        Identification: UnsupportedDomainAdapter(
            "Identification",
            "Identification has no corresponding class or property in domain/domain.loqi",
        ),
    }


def _resolve_action_ref(action_refs_by_role: dict[str, LoqiObjectRef], role: str) -> LoqiObjectRef:
    try:
        return action_refs_by_role[role]
    except KeyError as error:
        raise LoqiDomainMismatchError(f"Transition references unknown action role {role!r}") from error


def _transition_object_name(obj: TransitionDeclaration) -> str:
    if obj.parent is None:
        return f"transition_{obj.from_role}_to_{obj.to_role}"
    return f"transition_{obj.parent.name}_{obj.from_role}_to_{obj.to_role}"


def _action_spec_chain_head(
    transition: TransitionDeclaration, roles: list[str]
) -> ActionSpecChainPlaceholder:
    next_placeholder: ActionSpecChainPlaceholder | None = None
    for reverse_index, role in enumerate(reversed(roles)):
        index = len(roles) - reverse_index - 1
        next_placeholder = ActionSpecChainPlaceholder(
            transition=transition,
            role=role,
            index=index,
            next=next_placeholder,
        )
    if next_placeholder is None:
        raise LoqiDomainMismatchError("Transition to_when_absent cannot be an empty list")
    return next_placeholder


def _metadata_entries(ctx: LoqiAdapterContext, metadata: Metadata | None):
    if metadata is None:
        return ()
    entries: dict[str, Any] = {}
    if metadata.locale_trace_name is not None:
        entries["locale_trace_name"] = metadata.locale_trace_name
    if metadata.locale_pronoun is not None:
        entries["locale_pronoun"] = metadata.locale_pronoun
    entries.update(metadata.extra)
    return ctx.object_metadata(entries)


def _ensure_domain_supported(condition: bool, message: str) -> None:
    if not condition:
        raise LoqiDomainMismatchError(message)
