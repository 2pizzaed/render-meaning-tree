from __future__ import annotations

from textwrap import dedent

import pytest

from src.model.rules import (
    ActionDeclaration,
    Behaviour,
    CallStackAction,
    ConstraintsDeclaration,
    ConstructDeclaration,
    EffectDeclaration,
    InterruptionType,
    Metadata,
    TransitionDeclaration,
)
from src.serialization.loqi import (
    LoqiAdapterContext,
    LoqiAdapterNotFoundError,
    LoqiDomainMismatchError,
    LoqiObjectSpec,
    LoqiSerializationError,
    LoqiSerializer,
    serialize_loqi,
)


def test_serialize_loqi_construct_links_transitions_to_existing_actions() -> None:
    construct = ConstructDeclaration(
        name="if_statement",
        kind="branch",
        ast_node="IfStatement",
        actions=[
            ActionDeclaration(
                role="BEGIN",
                kind="marker",
                generalization="entry",
                effects=[EffectDeclaration(call_stack="add_frame")],
            ),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(
                from_role="BEGIN",
                to_role="END",
                constraints=ConstraintsDeclaration(condition_value=True, interruption_mode="none"),
            )
        ],
    )

    rendered = serialize_loqi(construct)

    assert rendered == dedent(
        """
        obj construct_if_statement : ConstructSpec {
            name = "if_statement";
            kind = "branch";
            hasActions(action_BEGIN);
            hasActions(action_END);
            hasTransitions(transition_BEGIN_to_END);
        }

        obj action_BEGIN : ActionSpec {
            role = "BEGIN";
            kind = "marker";
            generalization = "entry";
            hasEffects(effect_add_frame);
            belongsTo(construct_if_statement);
        }

        obj effect_add_frame : Effect {
            call_stack = CallStackAction:add_frame;
        }

        obj action_END : ActionSpec {
            role = "END";
            kind = "marker";
            belongsTo(construct_if_statement);
        }

        obj transition_BEGIN_to_END : TransitionSpec {
            from_(action_BEGIN);
            to_(action_END);
            hasConstraints(constraint_true_none);
            belongsTo(construct_if_statement);
        }

        obj constraint_true_none : Constraint {
            condition_value = OptionalBool:`true`;
            interruption_mode = InterruptionType:none;
        }
        """
    ).strip()


def test_serialize_loqi_to_when_absent_supports_single_and_many_roles() -> None:
    construct = ConstructDeclaration(
        name="loop",
        kind="cycle",
        ast_node="WhileStatement",
        actions=[
            ActionDeclaration(role="BEGIN", kind="marker"),
            ActionDeclaration(role="BODY", kind="step"),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="BODY", to_when_absent="END"),
            TransitionDeclaration(from_role="BODY", to_role="END", to_when_absent=["BEGIN", "END"]),
        ],
    )

    rendered = serialize_loqi(construct)

    assert "to_when_absent(action_END);" in rendered
    assert rendered.count("to_when_absent(") == 2
    assert "to_when_absent(action_BEGIN, action_END);" in rendered


def test_serialize_loqi_reuses_same_python_object_once() -> None:
    shared_effect = EffectDeclaration(interruption_start="break")
    construct = ConstructDeclaration(
        name="loop",
        kind="cycle",
        ast_node="ForStatement",
        actions=[
            ActionDeclaration(role="BEGIN", kind="marker", effects=[shared_effect]),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="END", effects=[shared_effect]),
        ],
    )

    rendered = serialize_loqi(construct)

    assert rendered.count("obj effect_break : Effect {") == 1
    assert "hasEffects(effect_break);" in rendered
    assert rendered.count("hasEffects(effect_break);") == 2


def test_serialize_loqi_allows_minimal_custom_registry_override() -> None:
    class GenericThing:
        def __init__(self, value: str) -> None:
            self.value = value

    class ExplicitThingAdapter:
        def object_name(self, obj):
            return f"thing_{obj.value}"

        def type_name(self, obj):
            return "ExplicitThing"

        def describe(self, obj, ctx):
            return LoqiObjectSpec(properties=(ctx.property("value", f"explicit:{obj.value}"),))

    adapters_by_type = {GenericThing: ExplicitThingAdapter()}

    rendered = serialize_loqi(GenericThing("x"), adapters_by_type=adapters_by_type)

    assert "obj thing_x : ExplicitThing {" in rendered
    assert 'value = "explicit:x";' in rendered
    assert "ExplicitThing" in rendered


def test_serialize_loqi_falls_back_to_type_based_name_when_adapter_has_no_object_name() -> None:
    class GenericThing:
        def __init__(self, value: str) -> None:
            self.value = value

    class MinimalThingAdapter:
        def type_name(self, obj):
            return "ExplicitThing"

        def describe(self, obj, ctx):
            return LoqiObjectSpec(properties=(ctx.property("value", obj.value),))

    rendered = serialize_loqi(GenericThing("x"), adapters_by_type={GenericThing: MinimalThingAdapter()})

    assert "obj ExplicitThing_obj_1 : ExplicitThing {" in rendered


def test_serialize_loqi_errors_for_unserializable_object() -> None:
    with pytest.raises(LoqiAdapterNotFoundError):
        serialize_loqi(object(), adapters_by_type={})


def test_serialize_loqi_errors_when_domain_class_is_missing() -> None:
    construct = ConstructDeclaration(
        name="branch",
        kind="if",
        ast_node="IfStatement",
        actions=[
            ActionDeclaration(
                role="COND",
                kind="condition",
                behaviour=Behaviour(assumed_value=True),
            )
        ],
    )

    with pytest.raises(LoqiDomainMismatchError, match="Behaviour"):
        serialize_loqi(construct)


def test_loqi_adapter_context_require_current_object_errors_without_object() -> None:
    ctx = LoqiAdapterContext(serializer=LoqiSerializer(adapters_by_type={}))

    with pytest.raises(LoqiSerializationError, match="Current Loqi object"):
        ctx.require_current_object()


def test_serialize_loqi_renders_object_metadata() -> None:
    construct = ConstructDeclaration(
        name="branch",
        kind="if",
        ast_node="IfStatement",
        metadata=Metadata(locale_trace_name="vetvlenie", extra={"hint": "demo"}),
    )

    rendered = serialize_loqi(construct)

    assert '} [ locale_trace_name = "vetvlenie" ; hint = "demo" ; ]' in rendered


def test_loqi_serializer_keeps_created_objects_in_objects_list() -> None:
    serializer = LoqiSerializer()
    construct = ConstructDeclaration(
        name="branch",
        kind="if",
        ast_node="IfStatement",
        actions=[ActionDeclaration(role="BEGIN", kind="marker")],
    )

    serializer.serialize(construct)

    assert [obj.object_id for obj in serializer.objects] == ["construct_branch", "action_BEGIN"]


def test_rules_declarations_coerce_domain_enums() -> None:
    effect = EffectDeclaration(interruption_start="break", call_stack="add_frame")
    constraint = ConstraintsDeclaration(condition_value=True, interruption_mode="none")

    assert effect.interruption_start is InterruptionType.BREAK
    assert effect.call_stack is CallStackAction.ADD_FRAME
    assert constraint.condition_value is True
    assert constraint.interruption_mode is InterruptionType.NONE


def test_serialize_loqi_renders_rule_enum_objects_as_loqi_enums() -> None:
    effect = EffectDeclaration(
        interruption_start=InterruptionType.BREAK,
        interruption_stop=InterruptionType.NONE,
        call_stack=CallStackAction.ADD_FRAME,
    )

    rendered = serialize_loqi(effect)

    assert "interruption_start = InterruptionType:break;" in rendered
    assert "interruption_stop = InterruptionType:none;" in rendered
    assert "call_stack = CallStackAction:add_frame;" in rendered
