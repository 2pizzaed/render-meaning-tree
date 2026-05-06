from unittest.mock import Mock

import pytest

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    Pipeline,
    PipelineRegistry,
    pipeline_stage,
)
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    Identification,
    TransitionDeclaration,
)
from src.model.situation import Action, Construct, TraceAct


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
        construct.end_action(),
        action,
    ]
    assert pipeline.trace_acts == [trace_act]


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


def test_domain_pipeline_fill_actions_adds_repeated_values_for_loop_control_condition():
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

    cond_actions = pipeline.get_actions_for(11)
    body_actions = pipeline.get_actions_for(12)
    assert len(cond_actions) == 1
    assert cond_actions[0].values == [True, False]
    assert len(body_actions) == 1
    assert body_actions[0].values == []


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
