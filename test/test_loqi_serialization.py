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
    LoqiObjectSpec,
    LoqiSerializationError,
    LoqiSerializer,
    LoqiVariableAssignment,
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
            is_opaque = false;
            generalization = "entry";
            belongsTo(construct_if_statement);
        }

        obj action_END : ActionSpec {
            role = "END";
            kind = "marker";
            is_opaque = false;
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
            interruption_start = InterruptionType:none;
            interruption_stop = InterruptionType:none;
            call_stack = CallStackAction:add_frame;
        }
        """
    ).strip()


def test_serialize_loqi_action_declaration_respects_explicit_opaque() -> None:
    action = ActionDeclaration(role="name", kind="identifier", opaque=False)

    rendered = serialize_loqi(action)

    assert "is_opaque = false;" in rendered


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

    assert [obj.object_id for obj in serializer.objects] == [
        "construct_branch",
        "action_BEGIN",
        "action_END",
    ]


def test_loqi_serializer_serializes_many_roots_once() -> None:
    serializer = LoqiSerializer()
    first = ConstructDeclaration(name="first", kind="compound", ast_node="First")
    second = ConstructDeclaration(name="second", kind="compound", ast_node="Second")

    serializer.serialize_many([first, second])
    rendered = serializer.render()

    assert rendered.count("obj construct_first : ConstructSpec {") == 1
    assert rendered.count("obj construct_second : ConstructSpec {") == 1


def test_serialize_loqi_renders_root_variable_name() -> None:
    construct = ConstructDeclaration(name="branch", kind="if", ast_node="IfStatement")

    rendered = serialize_loqi(construct, var_name="BranchRule")

    assert rendered.startswith("var BranchRule = obj construct_branch : ConstructSpec {")


def test_loqi_serializer_serializes_many_with_variable_names() -> None:
    serializer = LoqiSerializer()
    first = ConstructDeclaration(name="first", kind="compound", ast_node="First")
    second = ConstructDeclaration(name="second", kind="compound", ast_node="Second")

    serializer.serialize_many([first, second], variables={"FirstRule": first, "SecondRule": second})
    rendered = serializer.render()

    assert "var FirstRule = obj construct_first : ConstructSpec {" in rendered
    assert "var SecondRule = obj construct_second : ConstructSpec {" in rendered
    assert serializer.render_result().variables == (
        LoqiVariableAssignment(variable_name="FirstRule", object_id="construct_first"),
        LoqiVariableAssignment(variable_name="SecondRule", object_id="construct_second"),
    )
    assert not hasattr(serializer.objects[0], "variable_name")


def test_loqi_serializer_can_assign_variable_to_nested_object() -> None:
    action = ActionDeclaration(role="BEGIN", kind="marker")
    construct = ConstructDeclaration(
        name="branch",
        kind="if",
        ast_node="IfStatement",
        actions=[action],
    )

    serializer = LoqiSerializer()
    serializer.serialize_many([construct], variables={"BeginAction": action})
    rendered = serializer.render()

    assert "obj construct_branch : ConstructSpec {" in rendered
    assert "var BeginAction = obj action_BEGIN : ActionSpec {" in rendered


def test_loqi_serializer_rejects_invalid_variable_name() -> None:
    construct = ConstructDeclaration(name="branch", kind="if", ast_node="IfStatement")

    with pytest.raises(LoqiSerializationError, match="Invalid Loqi variable name"):
        serialize_loqi(construct, var_name="1Branch")


def test_loqi_serializer_rejects_variable_name_reuse() -> None:
    serializer = LoqiSerializer()
    first = ConstructDeclaration(name="first", kind="compound", ast_node="First")
    second = ConstructDeclaration(name="second", kind="compound", ast_node="Second")

    serializer.serialize(first, var_name="Rule")

    with pytest.raises(LoqiSerializationError, match="already assigned"):
        serializer.serialize(second, var_name="Rule")


def test_loqi_serializer_rejects_multiple_variables_for_same_object() -> None:
    construct = ConstructDeclaration(name="branch", kind="if", ast_node="IfStatement")

    with pytest.raises(LoqiSerializationError, match="already has variable"):
        LoqiSerializer().serialize_many([], variables={"FirstRule": construct, "SecondRule": construct})


def test_loqi_serializer_can_lookup_serialized_object_names_and_objects() -> None:
    serializer = LoqiSerializer()
    action = ActionDeclaration(role="BEGIN", kind="marker")
    construct = ConstructDeclaration(
        name="branch",
        kind="if",
        ast_node="IfStatement",
        actions=[action],
    )

    ref = serializer.serialize(construct)

    assert ref.object_id == "construct_branch"
    assert serializer.object_name(construct) == "construct_branch"
    assert serializer.object_name(action) == "action_BEGIN"
    assert serializer.object_by_name("construct_branch") is construct
    assert serializer.object_by_name("action_BEGIN") is action
    assert serializer.loqi_object_by_name("construct_branch") is serializer.objects[0]
    assert serializer.object_name(object()) is None
    assert serializer.object_by_name("missing") is None


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

    assert "obj construct_demo_ast10 : ConcreteConstruct {" in rendered
    assert "ast_id = 10;" in rendered
    assert 'ast_type = "node_10";' in rendered
    assert "derivedFrom(construct_demo);" in rendered
    assert "hasActions(demo_action_BEGIN_ast10);" in rendered
    assert "hasActions(demo_action_body_ast11);" in rendered
    assert "belongsTo(construct_demo_ast10);" in rendered
    assert "derivedFrom(action_body);" in rendered
    assert "jump_ast_id" not in rendered
    assert "hasValue(semantic_value_action_11_body_0);" in rendered
    assert "hasValue(semantic_value_action_11_body_1);" not in rendered
    assert "obj semantic_value_action_11_body_0 : SemanticValue {" in rendered
    assert "bool_value = true;" in rendered
    assert "directlyBeforeOf(semantic_value_action_11_body_1);" in rendered
    assert "directlyBeforeOf(demo_action_body_ast11);" in rendered


def test_serialize_loqi_situation_action_includes_inline_effects() -> None:
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
        values=[],
        rule=construct_rule.actions[1],
        parent=construct,
        owner=ctx,
        effects=EffectDeclaration(interruption_start=InterruptionType.RETURN),
    )
    ctx.add(construct)
    ctx.add(action)

    rendered = serialize_loqi(action, adapters_by_type=_all_model_adapters())

    assert "obj demo_action_body_ast11 : ConcreteAction {" in rendered
    assert "hasEffects(effect_return);" in rendered


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

    assert "obj act_root : TraceAct {" in rendered
    assert "hasAction(demo_trace_action_BEGIN_ast20);" in rendered
    assert "hasTransition(transition_demo_trace_BEGIN_to_body);" in rendered
    assert "directlyBeforeOf(act_demo_trace_body_1_ast21);" in rendered
    assert "hasValue(semantic_value_action_21_body_0);" in rendered
    assert "semantic_value_owner_" not in rendered



def test_serialize_loqi_situation_trace_state() -> None:
    rendered = serialize_loqi(
        TraceState(interruption_mode=InterruptionType.BREAK),
        adapters_by_type=_all_model_adapters(),
    )

    assert "obj trace_state : TraceState {" in rendered
    assert "interruption_mode = InterruptionType:break;" in rendered
