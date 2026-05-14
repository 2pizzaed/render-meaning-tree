from __future__ import annotations

from textwrap import dedent
from typing import Any
from unittest.mock import Mock

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
from src.model.situation import Action, Construct, TraceAct, TraceState
from src.serialization.adapters.rules import build_rules_loqi_adapters
from src.serialization.adapters.situation import build_situation_loqi_adapters
from src.serialization.loqi import (
    LoqiAdapter,
    LoqiAdapterContext,
    LoqiAdapterNotFoundError,
    LoqiDomainMismatchError,
    LoqiObjectSpec,
    LoqiSerializationError,
    LoqiSerializer,
    serialize_loqi,
)


def _all_model_adapters() -> dict[type[Any], LoqiAdapter[Any]]:
    return {
        **build_rules_loqi_adapters(),
        **build_situation_loqi_adapters(),
    }


class SituationContextStub:
    def __init__(self) -> None:
        self.code = Mock()
        self.rules: list[ConstructDeclaration] = []
        self.trace_acts: list[TraceAct] = []
        self.constructs: dict[int, Construct] = {}
        self.actions: dict[int, list[Action]] = {}
        self.code.get_node_by_id.side_effect = lambda ast_id: {
            "id": ast_id,
            "type": f"node_{ast_id}",
        }

    def get_construct_for(self, ast_id: int) -> Construct | None:
        return self.constructs.get(ast_id)

    def get_actions_for(self, ast_id: int) -> list[Action]:
        return self.actions.get(ast_id, []).copy()

    def get_related_actions(self, construct: Construct) -> list[Action]:
        return [
            action
            for actions in self.actions.values()
            for action in actions
            if action.parent is construct
        ]

    def add(self, object: Any) -> None:
        if isinstance(object, Construct):
            self.constructs[object.ast_id] = object
            return
        if isinstance(object, Action):
            if object.ast_id is None:
                return
            self.actions.setdefault(object.ast_id, []).append(object)
            return
        if isinstance(object, TraceAct):
            self.trace_acts.append(object)


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
                effects=EffectDeclaration(call_stack=CallStackAction.ADD_FRAME),
            ),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(
                from_role="BEGIN",
                to_role="END",
                constraints=ConstraintsDeclaration(condition_value=True, interruption_mode=InterruptionType.NONE),
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
            hasTransitions(transition_if_statement_BEGIN_to_END);
        }

        obj action_BEGIN : ActionSpec {
            role = "BEGIN";
            kind = "marker";
            generalization = "entry";
            belongsTo(construct_if_statement);
        }

        obj action_END : ActionSpec {
            role = "END";
            kind = "marker";
            belongsTo(construct_if_statement);
        }

        obj transition_if_statement_BEGIN_to_END : TransitionSpec {
            from_(action_BEGIN);
            to_(action_END);
            hasConstraints(constraint_true_none);
            hasEffects(effect_add_frame);
            belongsTo(construct_if_statement);
        }

        obj constraint_true_none : Constraint {
            condition_value = OptionalBool:`true`;
            interruption_mode = InterruptionType:none;
        }

        obj effect_add_frame : Effect {
            call_stack = CallStackAction:add_frame;
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
    assert rendered.count("to_when_absent(") == 3
    assert "to_when_absent(action_BEGIN);" in rendered
    assert "to_when_absent(action_BEGIN, action_END);" not in rendered


def test_serialize_loqi_omits_action_effect_but_keeps_transition_effect_relationship() -> None:
    shared_effect = EffectDeclaration(interruption_start=InterruptionType.BREAK)
    construct = ConstructDeclaration(
        name="loop",
        kind="cycle",
        ast_node="ForStatement",
        actions=[
            ActionDeclaration(role="BEGIN", kind="marker", effects=shared_effect),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="END", effects=shared_effect),
        ],
    )

    rendered = serialize_loqi(construct)

    assert rendered.count("obj effect_break : Effect {") == 1
    assert "hasEffects(effect_break);" in rendered
    assert rendered.count("hasEffects(effect_break);") == 1


def test_serialize_loqi_uses_compiled_transitions_for_construct_effects_and_generalization() -> None:
    construct = ConstructDeclaration(
        name="sequence",
        kind="compound",
        ast_node="Sequence",
        effects=EffectDeclaration(interruption_stop=InterruptionType.BREAK),
        actions=[
            ActionDeclaration(role="BEGIN", kind="marker"),
            ActionDeclaration(role="first", kind="step", generalization="item"),
            ActionDeclaration(role="next", kind="step", generalization="item"),
            ActionDeclaration(role="END", kind="marker"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )

    rendered = serialize_loqi(construct)

    assert "hasTransitions(transition_sequence_BEGIN_to_first);" in rendered
    assert "hasTransitions(transition_sequence_first_to_next);" in rendered
    assert "hasTransitions(transition_sequence_next_to_next);" in rendered
    assert "from_(action_item)" not in rendered
    assert "hasEffects(effect_break);" in rendered


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

    adapters_by_type: dict[type[Any], LoqiAdapter[Any]] = {GenericThing: ExplicitThingAdapter()}

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


def test_serialize_loqi_omits_rule_behaviour_relationship() -> None:
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

    rendered = serialize_loqi(construct)

    assert "hasBehaviour(" not in rendered


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


def test_loqi_serializer_serializes_many_roots_once() -> None:
    serializer = LoqiSerializer()
    first = ConstructDeclaration(name="first", kind="compound", ast_node="First")
    second = ConstructDeclaration(name="second", kind="compound", ast_node="Second")

    rendered = serializer.serialize_many([first, second])

    assert rendered.count("obj construct_first : ConstructSpec {") == 1
    assert rendered.count("obj construct_second : ConstructSpec {") == 1


def test_rules_declarations_coerce_domain_enums() -> None:
    effect = EffectDeclaration.from_dict({"interruption_start": "break", "call_stack": "add_frame"})
    constraint = ConstraintsDeclaration.from_dict({"condition_value": True, "interruption_mode": "none"})

    assert effect.interruption_start is InterruptionType.BREAK
    assert effect.call_stack is CallStackAction.ADD_FRAME
    assert constraint is not None
    assert constraint.condition_value is True
    assert constraint.interruption_mode is InterruptionType.NONE


def test_serialize_loqi_omits_missing_constraint_fields() -> None:
    rendered = serialize_loqi(ConstraintsDeclaration(condition_value=None))

    assert "condition_value = OptionalBool:`null`;" in rendered
    assert "interruption_mode = InterruptionType:any;" in rendered


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


def test_serialize_loqi_situation_construct_action_and_values() -> None:
    ctx = SituationContextStub()
    construct_rule = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="body", kind="inline"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=construct_rule, owner=ctx)
    action = Action(
        ast_id=11,
        values=[True, False],
        rule=construct_rule.actions[1],
        parent=construct,
        owner=ctx,
    )
    ctx.add(construct)
    ctx.add(action)

    rendered = serialize_loqi(construct, adapters_by_type=_all_model_adapters())

    assert "obj concrete_construct_10_demo : ConcreteConstruct {" in rendered
    assert "ast_id = 10;" in rendered
    assert 'ast_type = "node_10";' in rendered
    assert "derivedFrom(construct_demo);" in rendered
    assert "hasActions(concrete_action_10_BEGIN);" in rendered
    assert "hasActions(concrete_action_11_body);" in rendered
    assert "belongsTo(concrete_construct_10_demo);" in rendered
    assert "derivedFrom(action_body);" in rendered
    assert "jump_ast_id" not in rendered
    assert "obj semantic_value_action_11_body_0 : SemanticValue {" in rendered
    assert "bool_value = true;" in rendered
    assert "directlyBeforeOf(semantic_value_action_11_body_1);" in rendered
    assert "directlyBeforeOf(concrete_action_11_body);" in rendered


def test_serialize_loqi_situation_trace_act_links_transition_and_chain() -> None:
    ctx = SituationContextStub()
    transition = TransitionDeclaration(from_role="BEGIN", to_role="body")
    construct_rule = ConstructDeclaration(
        name="demo_trace",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="body", kind="inline"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[transition],
    )
    construct = Construct(parent=None, ast_id=20, rule=construct_rule, owner=ctx)
    action = Action(
        ast_id=21,
        values=[True],
        rule=construct_rule.actions[1],
        parent=construct,
        owner=ctx,
    )
    ctx.add(construct)
    ctx.add(action)
    first_trace = TraceAct(action=construct.begin_action(), used_transition=transition, situation=ctx)
    second_trace = TraceAct(action=action, used_transition=None, situation=ctx)
    ctx.add(first_trace)
    ctx.add(second_trace)

    rendered = serialize_loqi(first_trace, adapters_by_type=_all_model_adapters())

    assert "obj trace_act_0_20_BEGIN : TraceAct {" in rendered
    assert "hasAction(concrete_action_20_BEGIN);" in rendered
    assert "hasTransition(transition_demo_trace_BEGIN_to_body);" in rendered
    assert "directlyBeforeOf(trace_act_1_21_body);" in rendered
    assert "hasValue(semantic_value_action_21_body_0);" in rendered


def test_serialize_loqi_situation_expanded_from_is_single_link() -> None:
    ctx = SituationContextStub()
    parent_rule = ConstructDeclaration(
        name="parent",
        kind="compound",
        ast_node="parent_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="child", kind="compound"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    child_rule = ConstructDeclaration(
        name="child",
        kind="compound",
        ast_node="child_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    parent = Construct(parent=None, ast_id=30, rule=parent_rule, owner=ctx)
    child = Construct(parent=parent, ast_id=31, rule=child_rule, owner=ctx)
    parent_action = Action(
        ast_id=31,
        values=[],
        rule=parent_rule.actions[1],
        parent=parent,
        owner=ctx,
    )
    ctx.add(parent)
    ctx.add(child)
    ctx.add(parent_action)

    rendered = serialize_loqi(child, adapters_by_type=_all_model_adapters())

    assert "expandedFrom(action_child);" in rendered
    assert "expandedFrom(action_child," not in rendered


def test_serialize_loqi_situation_errors_when_expanded_from_has_multiple_sources() -> None:
    ctx = SituationContextStub()
    parent_rule = ConstructDeclaration(
        name="parent",
        kind="compound",
        ast_node="parent_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="left", kind="compound"),
            ActionDeclaration(role="right", kind="compound"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    child_rule = ConstructDeclaration(
        name="child",
        kind="compound",
        ast_node="child_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    parent = Construct(parent=None, ast_id=40, rule=parent_rule, owner=ctx)
    child = Construct(parent=parent, ast_id=41, rule=child_rule, owner=ctx)
    ctx.add(parent)
    ctx.add(child)
    ctx.add(Action(ast_id=41, values=[], rule=parent_rule.actions[1], parent=parent, owner=ctx))
    ctx.add(Action(ast_id=41, values=[], rule=parent_rule.actions[2], parent=parent, owner=ctx))

    with pytest.raises(LoqiDomainMismatchError, match="expands from multiple action specs"):
        serialize_loqi(child, adapters_by_type=_all_model_adapters())


def test_serialize_loqi_situation_trace_state() -> None:
    rendered = serialize_loqi(
        TraceState(interruption_mode=InterruptionType.BREAK),
        adapters_by_type=_all_model_adapters(),
    )

    assert "obj trace_state_break : TraceState {" in rendered
    assert "interruption_mode = InterruptionType:break;" in rendered
