from unittest.mock import Mock

import pytest

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    Pipeline,
    PipelineRegistry,
    pipeline_stage,
)
from src.generator.utilities import (
    collect_registry_objects,
    pipeline_to_loqi,
    registry_to_loqi,
    serialize_domain_objects_to_loqi,
)
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    EffectDeclaration,
    Identification,
    InterruptionType,
    TransitionDeclaration,
)
from src.model.situation import Action, Construct, TraceAct, TraceState


class ListRegistry(PipelineRegistry):
    def __init__(self):
        self.items: list[str] = []

    def collect(self) -> list[str]:
        return self.items.copy()


class RecordingPipeline(Pipeline):
    def __init__(self, *, fork_allowed: bool = True):
        super().__init__()
        self.registry = ListRegistry()
        self.fork_allowed = fork_allowed

    @property
    def current_result(self) -> PipelineRegistry:
        return self.registry

    def can_fork(self) -> bool:
        return self.fork_allowed and self.current_stage >= 2

    def _fork(self):
        child = type(self)(fork_allowed=self.fork_allowed)
        child.registry.items = self.registry.items.copy()
        return child

    @pipeline_stage(20)
    def second_stage(self):
        self.registry.items.append("second")

    @pipeline_stage(10)
    def first_stage(self):
        self.registry.items.append("first")

    @pipeline_stage(30)
    def third_stage(self):
        self.registry.items.append("third")


class OverriddenRecordingPipeline(RecordingPipeline):
    @pipeline_stage(10)
    def first_stage(self):
        self.registry.items.append("override")


def test_process_runs_stages_by_explicit_stage_number():
    pipeline = RecordingPipeline()

    pipeline.process()

    assert pipeline.current_result.collect() == ["first", "second", "third"]
    assert pipeline.current_stage == 30


def test_subclass_stage_override_replaces_base_stage():
    pipeline = OverriddenRecordingPipeline()

    pipeline.process()

    assert pipeline.current_result.collect() == ["override", "second", "third"]


def test_fork_uses_can_fork():
    pipeline = RecordingPipeline()

    assert not pipeline.can_fork()
    with pytest.raises(RuntimeError, match="Fork is forbidden"):
        pipeline.fork()

    pipeline.process()

    child = pipeline.fork()

    assert isinstance(child, RecordingPipeline)
    assert child.current_result.collect() == ["first", "second", "third"]


def test_domain_pipeline_can_disable_fork_with_flag():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager, fork_enabled=False)

    assert not pipeline.can_fork()
    with pytest.raises(RuntimeError, match="Fork is forbidden"):
        pipeline.fork()


def test_domain_pipeline_build_construct_skips_atomic_inline_and_noop_rules():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        ConstructDeclaration(name="root", kind="compound", ast_node="root_node"),
        ConstructDeclaration(name="atom", kind="inline", ast_node="atom_node"),
        ConstructDeclaration(name="ignored", kind="noop", ast_node="ignored_node"),
    ]

    assert pipeline._build_construct(2, {"id": 2, "type": "atom_node"}) is None
    assert pipeline._build_construct(3, {"id": 3, "type": "ignored_node"}) is None
    assert pipeline.registry.constructs == {}


def test_domain_pipeline_build_construct_keeps_external_noop_rule():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.ast.get_parent_of.return_value = None
    manager.get_node_by_id.side_effect = lambda ast_id: {
        "id": ast_id,
        "type": "external_node",
    }
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        ConstructDeclaration(
            name="external",
            kind="compound.external.noop",
            ast_node="external_node",
            actions=[ActionDeclaration(role="body", kind="compound")],
        ),
    ]

    construct = pipeline._build_construct(4, {"id": 4, "type": "external_node"})

    assert construct is not None
    assert construct.rule.name == "external"


def test_domain_pipeline_build_construct_keeps_inline_construct_with_explicit_actions():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.ast.get_parent_of.return_value = None
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "call_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        ConstructDeclaration(
            name="call",
            kind="inline.call",
            ast_node="call_node",
            actions=[
                ActionDeclaration(role="name", kind="identifier"),
                ActionDeclaration(role="func", kind="compound"),
            ],
        ),
    ]

    construct = pipeline._build_construct(2, {"id": 2, "type": "call_node"})

    assert construct is not None
    assert construct.rule.name == "call"


def test_domain_pipeline_first_construct_declaration_is_root_rule_without_parent():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.ast.get_parent_of.return_value = None
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "root_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        _construct_rule("root", "compound", "root_node"),
        _construct_rule("child", "compound", "child_node"),
    ]

    construct = pipeline._build_construct(1, {"id": 1, "type": "root_node"})

    assert construct is not None
    assert construct.parent is None
    assert construct.rule is pipeline.root_rule


def test_domain_pipeline_non_root_construct_requires_construct_parent():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.ast.get_parent_of.return_value = None
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        _construct_rule("root", "compound", "root_node"),
        _construct_rule("child", "compound", "child_node"),
    ]

    with pytest.raises(ValueError, match="Non-root construct 'child'.*has no parent construct"):
        pipeline._build_construct(2, {"id": 2, "type": "child_node"})


def test_domain_pipeline_uses_nearest_constructable_ancestor_as_parent():
    nodes = {
        1: {"id": 1, "type": "root_node"},
        2: {"id": 2, "type": "atom_node"},
        3: {"id": 3, "type": "child_node"},
    }
    parents = {3: nodes[2], 2: nodes[1], 1: None}
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.ast.get_parent_of.side_effect = lambda ast_id: parents[ast_id]
    manager.get_node_by_id.side_effect = lambda ast_id: nodes[ast_id]
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        _construct_rule("root", "compound", "root_node"),
        _construct_rule("atom", "inline", "atom_node"),
        _construct_rule("child", "compound", "child_node"),
    ]

    child = pipeline._build_construct(3, nodes[3])

    assert child is not None
    assert child.parent is pipeline.get_construct_for(1)
    assert child.parent is not None
    assert child.parent.rule is pipeline.root_rule


def _construct_rule(name: str, kind: str, ast_node: str) -> ConstructDeclaration:
    return ConstructDeclaration(
        name=name,
        kind=kind,
        ast_node=ast_node,
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )


def test_domain_pipeline_implements_situation_context_registry_methods():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="END", kind="END"),
            ActionDeclaration(role="body", kind="inline"),
        ],
    )

    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    action = Action(
        ast_id=11,
        values=[],
        rule=rule.actions[2],
        parent=construct,
        owner=pipeline,
    )
    trace_act = TraceAct(action=action, used_transition=None, situation=pipeline)
    pipeline.add(construct)
    pipeline.add(action)
    pipeline.add(trace_act)

    assert pipeline.code is manager
    assert pipeline.get_construct_for(10) is construct
    assert pipeline.get_construct_for(404) is None
    assert pipeline.get_actions_for(11) == [action]
    assert pipeline.get_related_actions(construct) == [
        construct.begin_action(),
        action,
        construct.end_action(),
    ]
    assert pipeline.trace_acts == [trace_act]
    assert isinstance(pipeline.registry.trace_state, TraceState)
    assert pipeline.registry.variables["S"] is pipeline.registry.trace_state


def test_situation_registry_can_be_used_directly_to_lookup_actions_and_store_trace_acts():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="body", kind="inline"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    action = Action(
        ast_id=11,
        values=[],
        rule=rule.actions[1],
        parent=construct,
        owner=pipeline,
    )
    pipeline.registry.add(construct)
    pipeline.registry.add(action)

    trace_act = TraceAct(
        action=pipeline.registry.require_action(ast_id=11, role="body", construct_ast_id=10),
        used_transition=None,
        situation=pipeline,
    )
    pipeline.registry.add(trace_act)

    assert pipeline.registry.get_construct_for(10) is construct
    assert pipeline.registry.find_actions(ast_id=11, role="body") == [action]
    assert trace_act.action is action
    assert pipeline.registry.trace_acts == [trace_act]


def test_situation_registry_require_action_rejects_ambiguous_matches():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="body", kind="inline"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.registry.add(construct)
    pipeline.registry.add(Action(ast_id=11, values=[], rule=rule.actions[1], parent=construct, owner=pipeline))
    pipeline.registry.add(Action(ast_id=12, values=[], rule=rule.actions[1], parent=construct, owner=pipeline))

    with pytest.raises(LookupError, match="Expected exactly one action"):
        pipeline.registry.require_action(role="body", construct_ast_id=10)


def test_situation_registry_collects_used_rules_before_situation_objects():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    used_rule = _construct_rule("used", "compound", "used_node")
    unused_rule = _construct_rule("unused", "compound", "unused_node")
    pipeline.registry.rules = [unused_rule, used_rule]

    construct = Construct(parent=None, ast_id=10, rule=used_rule, owner=pipeline)
    pipeline.add(construct)

    collected = pipeline.registry.collect()

    assert collected[0] is used_rule
    assert unused_rule not in collected
    assert collected.index(used_rule) < collected.index(construct)


def test_situation_registry_collects_rules_used_by_actions():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    parent_rule = _construct_rule("parent", "compound", "parent_node")
    action_rule_owner = _construct_rule("action_owner", "compound", "action_owner_node")
    action_rule = action_rule_owner.actions[0]
    pipeline.registry.rules = [parent_rule, action_rule_owner]

    construct = Construct(parent=None, ast_id=10, rule=parent_rule, owner=pipeline)
    action = Action(
        ast_id=11,
        values=[],
        rule=action_rule,
        parent=construct,
        owner=pipeline,
    )
    pipeline.add(construct)
    pipeline.add(action)

    collected = pipeline.registry.collect()

    assert collected[:2] == [parent_rule, action_rule_owner]
    assert collected.index(action_rule_owner) < collected.index(construct)
    assert collected.index(action_rule_owner) < collected.index(action)


def test_pipeline_to_loqi_serializes_each_registry_with_variable_map():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "demo_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = _construct_rule("demo", "compound", "demo_node")
    pipeline.registry.rules = [rule]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    rendered = pipeline_to_loqi(pipeline, variables={"DemoRule": rule})

    assert len(rendered) == 1
    serializer, loqi = rendered[0]
    assert serializer.object_name(rule) == "construct_demo"
    assert serializer.object_by_name("construct_demo") is rule
    assert "var DemoRule = obj construct_demo : ConstructSpec {" in loqi
    assert "var S = obj trace_state : TraceState {" in loqi


def test_registry_trace_state_is_singleton_and_can_be_replaced():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    initial_state = pipeline.registry.trace_state
    replacement = TraceState(InterruptionType.BREAK)

    pipeline.registry.add(replacement)

    assert pipeline.registry.trace_state is replacement
    assert initial_state not in pipeline.registry.collect()
    assert replacement in pipeline.registry.collect()
    assert pipeline.registry.variables["S"] is replacement


def test_registry_default_variables_can_be_overridden_by_call_variables():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    override_state = TraceState(InterruptionType.BREAK)

    rendered = pipeline_to_loqi(pipeline, variables={"S": override_state})

    serializer, loqi = rendered[0]
    assert serializer.object_name(override_state) == "trace_state_2"
    assert "var S = obj trace_state_2 : TraceState {" in loqi


def test_pipeline_to_loqi_keeps_forked_registries_separate():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "demo_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = _construct_rule("demo", "compound", "demo_node")
    pipeline.registry.rules = [rule]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.registry.add(construct)
    child = pipeline.fork()
    child.registry.add(
        TraceAct(
            action=child.registry.require_action(ast_id=10, role="BEGIN"),
            used_transition=None,
            situation=child,
        )
    )

    rendered = pipeline_to_loqi(pipeline)

    assert len(rendered) == 2
    assert "obj act_root : TraceAct {" not in rendered[0][1]
    assert "obj act_root : TraceAct {" in rendered[1][1]


def test_pipeline_registry_utilities_allow_editing_before_serialization():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "demo_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = _construct_rule("demo", "compound", "demo_node")
    pipeline.registry.rules = [rule]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.registry.add(construct)

    registries = pipeline.flatten_results()
    trace_act = TraceAct(
        action=registries[0].require_action(ast_id=10, role="BEGIN"),
        used_transition=None,
        situation=pipeline,
    )
    registries[0].add(trace_act)
    objects = collect_registry_objects(registries[0])
    serializer, rendered = serialize_domain_objects_to_loqi(objects, variables={"DemoRule": rule})

    assert serializer.object_name(trace_act) == "act_root"
    assert "var DemoRule = obj construct_demo : ConstructSpec {" in rendered
    assert "obj act_root : TraceAct {" in rendered


def test_registry_to_loqi_serializes_registry_roots():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {"id": ast_id, "type": "demo_node"}
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = _construct_rule("demo", "compound", "demo_node")
    pipeline.registry.rules = [rule]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.registry.add(construct)

    serializer, rendered = registry_to_loqi(pipeline.flatten_results()[0])

    assert serializer.object_name(construct) == "construct_demo_ast10"
    assert "obj construct_demo_ast10 : ConcreteConstruct {" in rendered


def test_action_possible_transitions_uses_compiled_concrete_transitions():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="sequence",
        kind="compound",
        ast_node="sequence_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="first", kind="inline", generalization="item"),
            ActionDeclaration(role="next", kind="inline", generalization="item"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    first_action = Action(
        ast_id=11,
        values=[],
        rule=rule.actions[1],
        parent=construct,
        owner=pipeline,
    )

    transitions = first_action.possible_transitions()

    assert [(transition.from_role, transition.to_role) for transition in transitions] == [("first", "next")]


def test_domain_pipeline_fill_actions_adds_loop_values_for_condition_actions():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "while_loop",
            "condition": {"id": 11, "type": "identifier"},
            "body": {"id": 12, "type": "compound_statement"},
        },
        11: {"id": 11, "type": "identifier"},
        12: {"id": 12, "type": "compound_statement"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="while_loop",
        kind="compound.loop",
        ast_node="while_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(
                role="cond",
                kind="inline.condition",
                identification=Identification(property="condition"),
            ),
            ActionDeclaration(
                role="body",
                kind="compound",
                identification=Identification(property="body"),
            ),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="cond"),
            TransitionDeclaration.from_dict(
                {
                    "from": "cond",
                    "to": "body",
                    "constraints": {"condition_value": True},
                }
            ),
            TransitionDeclaration(from_role="body", to_role="cond"),
            TransitionDeclaration.from_dict(
                {
                    "from": "cond",
                    "to": "END",
                    "constraints": {"condition_value": False},
                }
            ),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()
    pipeline._generate_bool_values()

    cond_actions = pipeline.get_actions_for(11)
    body_actions = pipeline.get_actions_for(12)
    assert len(cond_actions) == 1
    assert cond_actions[0].values == [True, True, False]
    assert len(body_actions) == 1
    assert body_actions[0].values == []


def test_domain_pipeline_fill_actions_adds_single_true_for_non_loop_condition():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "if_statement",
            "condition": {"id": 11, "type": "identifier"},
        },
        11: {"id": 11, "type": "identifier"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="if_structure",
        kind="compound.alternative",
        ast_node="if_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(
                role="cond",
                kind="inline.condition",
                identification=Identification(property="condition"),
            ),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()
    pipeline._generate_bool_values()

    cond_actions = pipeline.get_actions_for(11)
    assert len(cond_actions) == 1
    assert cond_actions[0].values == [True]


def test_domain_pipeline_fill_actions_creates_multiple_actions_for_self_loop_role():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "compound_statement",
            "statements": [
                {"id": 11, "type": "expression_statement"},
                {"id": 12, "type": "expression_statement"},
                {"id": 13, "type": "expression_statement"},
            ],
        },
        11: {"id": 11, "type": "expression_statement"},
        12: {"id": 12, "type": "expression_statement"},
        13: {"id": 13, "type": "expression_statement"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="block",
        kind="compound.sequence.block",
        ast_node="block_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(
                role="first",
                kind="auto",
                identification=Identification(property_path="statements / [0]"),
                generalization="item",
            ),
            ActionDeclaration(
                role="next",
                kind="auto",
                identification=Identification(origin="previous", property_path="[next]"),
                generalization="item",
            ),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()

    assert [action.rule.role for action in pipeline.get_actions_for(11)] == ["first"]
    assert [action.rule.role for action in pipeline.get_actions_for(12)] == ["next"]
    assert [action.rule.role for action in pipeline.get_actions_for(13)] == ["next"]


def test_domain_pipeline_fill_actions_skips_noop_nodes_without_materializing_concrete_action():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "compound_statement",
            "statements": [
                {"id": 11, "type": "comment"},
                {"id": 12, "type": "expression_statement"},
            ],
        },
        11: {"id": 11, "type": "comment"},
        12: {"id": 12, "type": "expression_statement"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="block",
        kind="compound.sequence.block",
        ast_node="block_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(
                role="first",
                kind="auto",
                identification=Identification(property_path="statements / [0]"),
                generalization="item",
            ),
            ActionDeclaration(
                role="next",
                kind="auto",
                identification=Identification(origin="previous", property_path="[next]"),
                generalization="item",
            ),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    pipeline.registry.rules = [
        rule,
        ConstructDeclaration(name="noop", kind="noop", ast_node="comment"),
        ConstructDeclaration(name="atom", kind="inline", ast_node="expression_statement"),
    ]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()

    assert pipeline.get_actions_for(11) == []
    visible_actions = pipeline.get_actions_for(12)
    assert [action.rule.role for action in visible_actions] == ["first"]


def test_domain_pipeline_fill_actions_skips_external_noop_inside_block_sequence():
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "compound_statement",
            "statements": [
                {"id": 11, "type": "function_definition"},
                {"id": 12, "type": "expression_statement"},
            ],
        },
        11: {"id": 11, "type": "function_definition"},
        12: {"id": 12, "type": "expression_statement"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="block",
        kind="compound.sequence.block",
        ast_node="block_node",
        actions=[
            ActionDeclaration(role="first", kind="auto", identification=Identification(property_path="statements / [0]"), generalization="item"),
            ActionDeclaration(role="next", kind="auto", identification=Identification(origin="previous", property_path="[next]"), generalization="item"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    pipeline.registry.rules = [
        rule,
        ConstructDeclaration(name="function", kind="compound.external.noop", ast_node="function_definition"),
        ConstructDeclaration(name="atom", kind="inline", ast_node="expression_statement"),
    ]
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()

    assert pipeline.get_actions_for(11) == []
    assert [action.rule.role for action in pipeline.get_actions_for(12)] == ["first"]


def test_domain_pipeline_fill_actions_materializes_inline_construct_effects_on_concrete_action():
    manager = Mock(language="python")
    manager.ast.instanceof.return_value = False
    manager.get_node_by_id.side_effect = lambda ast_id: {
        10: {
            "id": 10,
            "type": "root_node",
            "body": {"id": 11, "type": "return_statement"},
        },
        11: {"id": 11, "type": "return_statement"},
    }.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        ConstructDeclaration(
            name="root",
            kind="compound",
            ast_node="root_node",
            actions=[
                ActionDeclaration(role="BEGIN", kind="BEGIN"),
                ActionDeclaration(
                    role="body",
                    kind="inline",
                    identification=Identification(property="body"),
                ),
                ActionDeclaration(role="END", kind="END"),
            ],
            transitions=[TransitionDeclaration(from_role="BEGIN", to_role="body")],
        ),
        ConstructDeclaration(
            name="return_action",
            kind="inline",
            ast_node="return_statement",
            effects=EffectDeclaration(interruption_start=InterruptionType.RETURN),
        ),
    ]
    construct = Construct(parent=None, ast_id=10, rule=pipeline.registry.rules[0], owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()

    action = pipeline.registry.require_action(ast_id=11, role="body", construct_ast_id=10)
    assert action.effects is not None
    assert action.effects.interruption_start is InterruptionType.RETURN


def test_domain_pipeline_fill_actions_expands_inline_call_content_from_inner_to_outer():
    nodes = {
        10: {
            "id": 10,
            "type": "assignment_statement",
            "right": {
                "id": 11,
                "type": "function_call",
                "function": {"type": "identifier", "repr_name": "outer"},
                "arguments": [
                    {
                        "id": 12,
                        "type": "function_call",
                        "function": {"type": "identifier", "repr_name": "inner"},
                    }
                ],
            },
        },
        11: {
            "id": 11,
            "type": "function_call",
            "function": {"type": "identifier", "repr_name": "outer"},
        },
        12: {
            "id": 12,
            "type": "function_call",
            "function": {"type": "identifier", "repr_name": "inner"},
        },
    }
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: nodes.get(ast_id)
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.registry.rules = [
        ConstructDeclaration(
            name="inline_compound_atom",
            kind="inline.compound",
            ast_node="assignment_statement",
            actions=[
                ActionDeclaration(role="content", kind="auto"),
            ],
            transitions=[
                TransitionDeclaration(from_role="BEGIN", to_role="content"),
                TransitionDeclaration(
                    from_role="content",
                    to_role="content",
                    to_when_absent="END",
                ),
            ],
        ),
        ConstructDeclaration(
            name="function_call",
            kind="inline.call",
            ast_node="function_call",
            actions=[
                ActionDeclaration(role="func", kind="compound"),
            ],
        ),
    ]
    construct = Construct(
        parent=None,
        ast_id=10,
        rule=pipeline.registry.rules[0],
        owner=pipeline,
    )
    pipeline.add(construct)

    pipeline._fill_actions()

    content_actions = [
        action for action in construct.actions if action.rule.role == "content"
    ]
    assert [action.ast_id for action in content_actions] == [12, 11]


def test_domain_pipeline_function_call_lookup_returns_definition_node_for_declaration():
    nodes = {
        10: {
            "id": 10,
            "type": "function_call",
            "function": {"type": "identifier", "repr_name": "add"},
        },
        14: {"id": 14, "type": "function_declaration", "name": "add"},
        15: {
            "id": 15,
            "type": "function_definition",
            "declaration": {"id": 14, "type": "function_declaration", "name": "add"},
        },
    }
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: nodes.get(ast_id)
    manager.user_defined_function_names = {"add": 14}
    manager.ast.get_parent_of.side_effect = lambda ast_id: nodes[15] if ast_id == 14 else None

    call_path = Mock()
    call_path.instanceof.side_effect = lambda node_type: node_type == "function_call"
    call_path.get.return_value = nodes[10]
    manager.ast.get_path.return_value = call_path

    pipeline = DomainDataGeneratorPipeline(manager)
    construct = Construct(
        parent=None,
        ast_id=10,
        rule=ConstructDeclaration(
            name="function_call",
            kind="inline.call",
            ast_node="function_call",
            actions=[ActionDeclaration(role="func", kind="compound")],
        ),
        owner=pipeline,
    )

    found, path = pipeline._lookup_node_without_identification(
        construct,
        construct.rule.action_declaration_by_role("func"),  # type: ignore[arg-type]
        previous_path=None,
    )

    assert found is nodes[15]
    assert path is None


def test_domain_pipeline_fill_actions_materializes_external_noop_outside_program_or_block():
    nodes = {
        10: {
            "id": 10,
            "type": "function_call",
            "function": {"type": "identifier", "repr_name": "add"},
        },
        14: {"id": 14, "type": "function_declaration", "name": "add"},
        15: {
            "id": 15,
            "type": "function_definition",
            "declaration": {"id": 14, "type": "function_declaration", "name": "add"},
        },
    }
    manager = Mock(language="python")
    manager.get_node_by_id.side_effect = lambda ast_id: nodes.get(ast_id)
    manager.user_defined_function_names = {"add": 14}
    manager.ast.get_parent_of.side_effect = lambda ast_id: nodes[15] if ast_id == 14 else None

    call_path = Mock()
    call_path.instanceof.side_effect = lambda node_type: node_type == "function_call"
    call_path.get.return_value = nodes[10]
    manager.ast.get_path.return_value = call_path

    pipeline = DomainDataGeneratorPipeline(manager)
    call_rule = ConstructDeclaration(
        name="function_call",
        kind="inline.call",
        ast_node="function_call",
        actions=[ActionDeclaration(role="func", kind="compound")],
        transitions=[TransitionDeclaration(from_role="BEGIN", to_role="func")],
    )
    pipeline.registry.rules = [
        call_rule,
        ConstructDeclaration(
            name="function",
            kind="compound.external.noop",
            ast_node="function_definition",
        ),
    ]
    construct = Construct(parent=None, ast_id=10, rule=call_rule, owner=pipeline)
    pipeline.add(construct)

    pipeline._fill_actions()

    assert [action.rule.role for action in pipeline.get_actions_for(15)] == ["func"]


def test_domain_pipeline_fork_copies_situation_context_registry_state():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager)
    rule = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="END", kind="END"),
        ],
    )
    construct = Construct(parent=None, ast_id=10, rule=rule, owner=pipeline)
    pipeline.add(construct)

    child = pipeline.fork()

    assert child.get_construct_for(10) is construct
    assert child.get_actions_for(10) == pipeline.get_actions_for(10)
    assert child.trace_acts == []
