import pytest

from src.generator.automaton import (
    AmbiguousTransitionError,
    ConstructAutomatonValidationError,
    ConstructTransitionAutomaton,
)
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    TransitionDeclaration,
)


def test_construct_automaton_iterates_linear_steps_without_callback():
    automaton = ConstructTransitionAutomaton(
        ConstructDeclaration(
            name="simple",
            kind="compound",
            ast_node="simple_node",
            actions=[
                ActionDeclaration(role="BEGIN", kind="BEGIN"),
                ActionDeclaration(role="body", kind="inline"),
                ActionDeclaration(role="END", kind="END"),
            ],
            transitions=[
                TransitionDeclaration(from_role="BEGIN", to_role="body"),
                TransitionDeclaration(from_role="body", to_role="END"),
            ],
        )
    )

    steps = list(automaton.iter_steps())

    assert [step.role for step in steps] == ["body", "END"]
    assert [step.role for step in automaton.iter_steps(include_begin=True)] == ["BEGIN", "body", "END"]


def test_construct_automaton_first_and_next_step_are_simple_to_use():
    automaton = ConstructTransitionAutomaton(
        ConstructDeclaration(
            name="simple",
            kind="compound",
            ast_node="simple_node",
            actions=[
                ActionDeclaration(role="BEGIN", kind="BEGIN"),
                ActionDeclaration(role="body", kind="inline"),
                ActionDeclaration(role="END", kind="END"),
            ],
            transitions=[
                TransitionDeclaration(from_role="BEGIN", to_role="body"),
                TransitionDeclaration(from_role="body", to_role="END"),
            ],
        )
    )

    first = automaton.first_step()
    second = automaton.next_step(first)
    done = automaton.next_step(second) if second is not None else None

    assert first.role == "body"
    assert second is not None
    assert second.role == "END"
    assert done is None


def test_construct_automaton_adds_absent_transition_for_optional_target():
    construct = ConstructDeclaration(
        name="for_loop",
        kind="compound.loop",
        ast_node="for_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="init", kind="inline.optional"),
            ActionDeclaration(role="cond", kind="inline.condition"),
            ActionDeclaration(role="body", kind="compound"),
            ActionDeclaration(role="update", kind="inline.optional"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="init"),
            TransitionDeclaration(from_role="init", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="body"),
            TransitionDeclaration(from_role="body", to_role="update"),
            TransitionDeclaration(from_role="update", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="END"),
        ],
    )

    automaton = ConstructTransitionAutomaton(construct)

    assert automaton.transitions_from("BEGIN")[0].to_when_absent == "cond"
    assert automaton.transitions_from("body")[0].to_when_absent == "cond"


def test_construct_automaton_rejects_optional_target_without_skip_path():
    construct = ConstructDeclaration(
        name="bad_optional",
        kind="compound",
        ast_node="bad_optional_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="maybe", kind="inline.optional"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="maybe"),
        ],
    )

    with pytest.raises(ConstructAutomatonValidationError, match="optional action"):
        ConstructTransitionAutomaton(construct)


def test_construct_automaton_marks_self_loop_iterations_with_explicit_step():
    construct = ConstructDeclaration(
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
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    automaton = ConstructTransitionAutomaton(construct)

    first = automaton.first_step()
    next_step = automaton.next_step(first)
    repeated_next = automaton.step(next_step, next_step.outgoing_transitions[0]) if next_step is not None else None

    assert first.role == "first"
    assert not first.starts_loop_iteration
    assert next_step is not None
    assert next_step.role == "next"
    assert next_step.starts_loop_iteration
    assert not next_step.ends_loop_iteration
    assert repeated_next is not None
    assert repeated_next.starts_loop_iteration
    assert repeated_next.ends_loop_iteration
    assert repeated_next.loop is not None
    assert repeated_next.loop.exit_roles == frozenset({"END"})


def test_construct_automaton_marks_multi_action_loop_iteration_boundary():
    construct = ConstructDeclaration(
        name="while_loop",
        kind="compound.loop",
        ast_node="while_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="cond", kind="inline.condition"),
            ActionDeclaration(role="body", kind="compound"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="body"),
            TransitionDeclaration(from_role="body", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="END"),
        ],
    )
    automaton = ConstructTransitionAutomaton(construct)

    cond = automaton.first_step()
    body = automaton.step(cond, automaton.transitions_from("cond")[0])
    repeated_cond = automaton.next_step(body)

    assert cond.role == "cond"
    assert cond.starts_loop_iteration
    assert not cond.ends_loop_iteration
    assert body.role == "body"
    assert not body.starts_loop_iteration
    assert not body.ends_loop_iteration
    assert repeated_cond is not None
    assert repeated_cond.role == "cond"
    assert repeated_cond.starts_loop_iteration
    assert repeated_cond.ends_loop_iteration


def test_construct_automaton_detects_loop_control_action_by_condition_constraints():
    construct = ConstructDeclaration(
        name="while_loop",
        kind="compound.loop",
        ast_node="while_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="cond", kind="inline.condition"),
            ActionDeclaration(role="body", kind="compound"),
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
    automaton = ConstructTransitionAutomaton(construct)

    controls = automaton.loop_controls()

    assert len(controls) == 1
    assert controls[0].role == "cond"
    assert controls[0].condition_values == (True, False)
    cond = construct.action_declaration_by_role("cond")
    assert cond is not None
    assert automaton.controls_loop(cond)
    assert automaton.repeated_value_roles == frozenset({"cond"})


def test_construct_automaton_detects_sequential_loops():
    construct = ConstructDeclaration(
        name="two_loops",
        kind="compound.sequence",
        ast_node="two_loops_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="first", kind="inline"),
            ActionDeclaration(role="second", kind="inline"),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="first", to_role="first", to_when_absent="second"),
            TransitionDeclaration(from_role="second", to_role="second", to_when_absent="END"),
        ],
    )
    automaton = ConstructTransitionAutomaton(construct)

    loop_roles = {loop.roles for loop in automaton.loops}

    assert loop_roles == {frozenset({"first"}), frozenset({"second"})}
    assert automaton.first_step().starts_loop_iteration


def test_construct_automaton_detects_self_loop_until_absent_control():
    construct = ConstructDeclaration(
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
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )
    automaton = ConstructTransitionAutomaton(construct)

    controls = automaton.self_loop_controls()

    assert len(controls) == 1
    assert controls[0].role == "next"
    assert controls[0].absent_roles == ("END",)
    assert automaton.repeated_action_roles == frozenset({"next"})
    next_action = construct.action_declaration_by_role("next")
    assert next_action is not None
    assert automaton.repeats_action(next_action)


def test_construct_automaton_rejects_non_terminating_loop():
    construct = ConstructDeclaration(
        name="bad_loop",
        kind="compound.loop",
        ast_node="bad_loop_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="cond", kind="inline.condition"),
            ActionDeclaration(role="body", kind="compound"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="cond"),
            TransitionDeclaration(from_role="cond", to_role="body"),
            TransitionDeclaration(from_role="body", to_role="cond"),
        ],
    )

    with pytest.raises(ConstructAutomatonValidationError, match="non-terminating"):
        ConstructTransitionAutomaton(construct)


def test_construct_automaton_rejects_multiple_begin_transitions():
    construct = ConstructDeclaration(
        name="bad_begin",
        kind="compound",
        ast_node="bad_begin_node",
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN"),
            ActionDeclaration(role="left", kind="inline"),
            ActionDeclaration(role="right", kind="inline"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="left"),
            TransitionDeclaration(from_role="BEGIN", to_role="right"),
        ],
    )

    with pytest.raises(ConstructAutomatonValidationError, match=r"exactly one \(or zero\) transition from BEGIN"):
        ConstructTransitionAutomaton(construct)


def test_construct_automaton_requires_explicit_transition_for_branching():
    automaton = ConstructTransitionAutomaton(
        ConstructDeclaration(
            name="branching",
            kind="compound",
            ast_node="branching_node",
            actions=[
                ActionDeclaration(role="BEGIN", kind="BEGIN"),
                ActionDeclaration(role="cond", kind="inline.condition"),
                ActionDeclaration(role="body", kind="compound"),
                ActionDeclaration(role="END", kind="END"),
            ],
            transitions=[
                TransitionDeclaration(from_role="BEGIN", to_role="cond"),
                TransitionDeclaration(from_role="cond", to_role="body"),
                TransitionDeclaration(from_role="cond", to_role="END"),
            ],
        )
    )
    cond = automaton.first_step()

    with pytest.raises(AmbiguousTransitionError, match="choose one explicitly"):
        automaton.next_step(cond)

    assert automaton.step(cond, cond.outgoing_transitions[1]).role == "END"


def test_construct_automaton_to_dot_uses_action_roles_and_compiled_edges():
    construct = ConstructDeclaration(
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
            TransitionDeclaration(from_role="BEGIN", to_role="first"),
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent="END"),
        ],
    )

    dot = ConstructTransitionAutomaton(construct).to_dot()

    assert '"BEGIN" -> "first";' in dot
    assert '"first" -> "next";' in dot
    assert '"next" -> "next";' in dot
    assert '"next" -> "END" [style="dashed", label="absent"];' in dot
    assert "item" not in dot
