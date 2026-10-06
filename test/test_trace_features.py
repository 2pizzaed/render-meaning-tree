from collections.abc import Iterator

import pytest

from src.generator.concepts import CONCEPT_PREDICATES, CONCEPTS, collect_concepts
from src.generator.skills import (
    ERRORNEOUS_SKILLS,
    SKILL_PREDICATES,
    collect_skills,
    is_everything_evaluated,
)
from src.helpers.bitflags import pack_flags
from src.model.rules import (
    ConstraintsDeclaration,
    EffectDeclaration,
    InterruptionType,
    TransitionDeclaration,
)
from src.model.situation import SemanticValue
from src.types import Node
from test.helpers.trace import TraceBuilder, ast_node


@pytest.fixture(autouse=True)
def local_node_hierarchy(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("src.ast_managers.node_type_hierarchy", {})
    yield


def test_empty_trace_has_no_features() -> None:
    builder = TraceBuilder(ast_node(1, "program_entry_point", body=[]))
    assert collect_concepts(builder.ast, []) == set()
    assert collect_skills(builder.ast, []) == set()
    assert set(SKILL_PREDICATES) == ERRORNEOUS_SKILLS
    assert set(CONCEPT_PREDICATES) == {
        name
        for group, flags in CONCEPTS.items()
        for name in (flags if isinstance(flags, dict) else [group])
    }


def test_inactive_bodies_do_not_contribute_concepts() -> None:
    executed = ast_node(4, "assignment_statement", value=ast_node(5, "add_operator"))
    skipped = ast_node(
        6, "compound_statement", statements=[ast_node(7, "delete_statement")]
    )
    condition = ast_node(3, "identifier", name="ready")
    alternative = ast_node(
        2,
        "if_statement",
        branches=[
            ast_node(
                8,
                "condition_branch",
                condition=condition,
                body=ast_node(9, "compound_statement", statements=[executed]),
            ),
        ],
        elseBranch=skipped,
    )
    uncalled = ast_node(
        10, "function_definition", body=ast_node(11, "return_statement")
    )
    builder = TraceBuilder(
        ast_node(1, "program_entry_point", body=[alternative, uncalled])
    )
    program = builder.construct(1, name="global_statements_structure")
    branch = builder.construct(2, kind="compound.alternative", parent=program)
    builder.act(program.begin_action())
    builder.act(branch.begin_action())
    builder.act(builder.action(3, branch, role="first_cond", kind="inline.condition"))
    builder.act(builder.action(4, branch))
    assert collect_concepts(builder.ast, builder.trace) == {
        "if",
        "assignment",
        "arithmetic",
    }


@pytest.mark.parametrize(
    ("concept", "node_type"),
    [
        ("pointers", "pointer_unpack"),
        ("bitwise", "xor_operator"),
        ("member_access", "member_access"),
        ("arrays", "array_literal"),
        ("type_casts", "cast_type_expression"),
        ("io", "input_command"),
        ("logical", "not_operator"),
        ("arithmetic", "mul_operator"),
        ("ternary_conditions", "ternary_operator"),
        ("lib_function_call", "memory_free_call"),
        ("var_declaration", "variable_declaration"),
        ("assignment", "assignment_expression"),
        ("delete", "delete_statement"),
        ("strings", "string_literal"),
        ("list_collections", "list_literal"),
        ("map_collections", "dictionary_literal"),
        ("object_new", "object_new_expression"),
        ("function", "function_definition"),
        ("structure", "structure_definition"),
        ("interface", "interface_definition"),
        ("class", "class_definition"),
        ("field", "field_declaration"),
        ("method", "method_definition"),
        ("constructor", "constructor_call"),
        ("destructor", "destructor_call"),
        ("generic_type", "generic_class_type"),
        ("return", "return_statement"),
        ("general_for_loop", "general_for_loop"),
        ("range_for_loop", "range_for_loop"),
        ("for_each_loop", "for_each_loop"),
        ("while_loop", "while_loop"),
        ("do_while_loop", "do_while_loop"),
        ("infinite_loop", "infinite_loop"),
        ("break", "break_statement"),
        ("continue", "continue_statement"),
        ("if", "if_statement"),
        ("switch", "switch_statement"),
        ("fallthrough_case", "fallthrough_case_block"),
        ("default_case", "default_case_block"),
    ],
)
def test_concepts_require_trace_evidence(concept: str, node_type: str) -> None:
    builder = TraceBuilder(
        ast_node(1, "program_entry_point", body=[ast_node(2, node_type)])
    )
    root = builder.construct(
        1, name="global_statements_structure", kind="compound.sequence.program"
    )
    builder.act(root.begin_action())
    predicate = CONCEPT_PREDICATES[concept]
    assert not predicate(builder.ast, builder.trace)
    builder.act(builder.action(2, root))
    assert predicate(builder.ast, builder.trace)
    assert pack_flags(CONCEPTS, collect_concepts(builder.ast, builder.trace)) > 0


@pytest.mark.parametrize("node_type", ["assignment_statement", "assignment_expression"])
@pytest.mark.parametrize(
    ("operator", "concept"),
    [
        ("none", None),
        ("add", "arithmetic"),
        ("sub", "arithmetic"),
        ("mul", "arithmetic"),
        ("div", "arithmetic"),
        ("floor_div", "arithmetic"),
        ("mod", "arithmetic"),
        ("pow", "arithmetic"),
        ("bitwise_and", "bitwise"),
        ("bitwise_or", "bitwise"),
        ("bitwise_xor", "bitwise"),
        ("bitwise_shift_left", "bitwise"),
        ("bitwise_shift_right", "bitwise"),
    ],
)
def test_augmented_assignments_include_their_operator_concept(
    node_type: str, operator: str, concept: str | None
) -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(2, node_type, augmented_operator=operator),
            ],
        )
    )
    root = builder.construct(1)
    builder.act(builder.action(2, root))
    expected = {"assignment"} if concept is None else {"assignment", concept}
    assert collect_concepts(builder.ast, builder.trace) == expected


def test_only_entered_else_and_checked_elseif_are_detected() -> None:
    alternative = ast_node(
        2,
        "if_statement",
        branches=[
            ast_node(
                3,
                "condition_branch",
                condition=ast_node(4, "identifier"),
                body=ast_node(
                    5, "compound_statement", statements=[ast_node(6, "string_literal")]
                ),
            ),
            ast_node(
                7,
                "condition_branch",
                condition=ast_node(8, "identifier"),
                body=ast_node(9, "compound_statement", statements=[]),
            ),
        ],
        elseBranch=ast_node(
            10, "compound_statement", statements=[ast_node(11, "dictionary_literal")]
        ),
    )
    builder = TraceBuilder(ast_node(1, "program_entry_point", body=[alternative]))
    root = builder.construct(1)
    branch = builder.construct(2, kind="compound.alternative", parent=root)
    builder.act(branch.begin_action())
    builder.act(builder.action(4, branch, role="first_cond", kind="inline.condition"))
    assert collect_concepts(builder.ast, builder.trace) == {"if"}
    builder.act(builder.action(8, branch, role="next_cond", kind="inline.condition"))
    assert collect_concepts(builder.ast, builder.trace) == {"if", "elseif"}
    builder.act(builder.action(10, branch, role="else_branch", kind="compound"))
    builder.act(builder.action(11, branch))
    assert collect_concepts(builder.ast, builder.trace) == {
        "if",
        "elseif",
        "else",
        "map_collections",
    }


@pytest.mark.parametrize(
    "expression",
    [
        ast_node(
            3,
            "short_circuit_and_operator",
            left_operand=ast_node(4, "identifier"),
            right_operand=ast_node(5, "delete_expression"),
        ),
        ast_node(
            3,
            "ternary_operator",
            condition=ast_node(4, "identifier"),
            true_expression=ast_node(5, "delete_expression"),
            false_expression=ast_node(6, "dictionary_literal"),
        ),
    ],
)
def test_conditional_operands_need_their_own_evidence(expression: Node) -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(2, "assignment_statement", value=expression),
            ],
        )
    )
    root = builder.construct(1)
    builder.act(builder.action(2, root))
    assert "assignment" in collect_concepts(builder.ast, builder.trace)
    assert "delete" not in collect_concepts(builder.ast, builder.trace)
    assert "map_collections" not in collect_concepts(builder.ast, builder.trace)
    builder.act(builder.action(5, root))
    assert "delete" in collect_concepts(builder.ast, builder.trace)


def test_plain_actions_exercise_repeat_and_order_without_mutating_values() -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(2, "assignment_statement"),
                ast_node(3, "assignment_statement"),
            ],
        )
    )
    root = builder.construct(
        1, name="global_statements_structure", kind="compound.sequence.program"
    )
    builder.act(root.begin_action())
    action = builder.action(2, root)
    action.values = [SemanticValue(True, used=True), SemanticValue(False)]
    action.bind_values()
    first = builder.act(action, value=action.values[0])
    assert collect_skills(builder.ast, builder.trace) == {"passed_action_repeat"}
    builder.act(builder.action(3, root))
    before = tuple(builder.trace)
    assert collect_skills(builder.ast, builder.trace) == {
        "passed_action_repeat",
        "actions_in_order",
    }
    assert tuple(builder.trace) == before
    assert first.value is action.values[0]
    assert [value.used for value in action.values] == [True, False]
    assert builder.registry.variables == {"S": builder.registry.trace_state}


def test_condition_skill_requires_a_used_transition_not_unused_values() -> None:
    builder = TraceBuilder(
        ast_node(1, "while_loop", condition=ast_node(2, "identifier"))
    )
    loop = builder.construct(1, kind="compound.loop")
    builder.act(loop.begin_action())
    condition = builder.action(2, loop, role="cond", kind="inline.condition")
    condition.values = [SemanticValue(False)]
    condition.bind_values()
    builder.act(condition, value=condition.values[0])
    assert "condition_value_selects_next" not in collect_skills(
        builder.ast, builder.trace
    )
    assert "loop_iteration" not in collect_concepts(builder.ast, builder.trace)
    builder.act(
        loop.end_action(),
        transition=TransitionDeclaration(
            "cond",
            "END",
            constraints=ConstraintsDeclaration(condition_value=False),
        ),
    )
    assert "condition_value_selects_next" in collect_skills(builder.ast, builder.trace)


def test_loop_iteration_requires_entering_the_body() -> None:
    builder = TraceBuilder(
        ast_node(1, "while_loop", body=ast_node(2, "compound_statement", statements=[]))
    )
    loop = builder.construct(1, kind="compound.loop")
    builder.act(loop.begin_action())
    assert collect_concepts(builder.ast, builder.trace) == {"while_loop"}
    builder.act(builder.action(2, loop, role="body", kind="compound"))
    assert collect_concepts(builder.ast, builder.trace) == {
        "while_loop",
        "loop_iteration",
    }


@pytest.mark.parametrize("recursive", [False, True])
def test_repeated_calls_are_distinct_from_recursion(recursive: bool) -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(
                    2,
                    "function_definition",
                    body=ast_node(3, "compound_statement", statements=[]),
                ),
            ],
        )
    )
    root = builder.construct(1)
    function = builder.construct(
        2, name="func_def_structure", kind="compound.external.noop", parent=root
    )
    builder.act(function.begin_action())
    if not recursive:
        builder.act(function.end_action())
    builder.act(function.begin_action())
    concepts = collect_concepts(builder.ast, builder.trace)
    assert ("recursion" in concepts) is recursive
    assert ("call_depth" in concepts) is recursive
    assert "function_body_runs_on_call" in collect_skills(builder.ast, builder.trace)
    builder.act(function.end_action())
    assert "function_not_resumed_after_exit" in collect_skills(
        builder.ast, builder.trace
    )


def test_mutual_recursion_uses_active_function_stack() -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(2, "function_definition"),
                ast_node(3, "function_definition"),
            ],
        )
    )
    root = builder.construct(1)
    first = builder.construct(2, kind="compound.external.noop", parent=root)
    second = builder.construct(3, kind="compound.external.noop", parent=root)
    builder.act(first.begin_action())
    builder.act(second.begin_action())
    assert "call_depth" in collect_concepts(builder.ast, builder.trace)
    assert "recursion" not in collect_concepts(builder.ast, builder.trace)
    builder.act(first.begin_action())
    assert "recursion" in collect_concepts(builder.ast, builder.trace)


def test_unknown_function_is_not_assumed_to_be_a_library_call() -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(
                    2,
                    "function_call",
                    function=ast_node(3, "identifier", name="unknown"),
                ),
                ast_node(
                    4,
                    "function_definition",
                    declaration=ast_node(5, "function_declaration"),
                ),
            ],
        )
    )
    root = builder.construct(1)
    builder.act(builder.action(2, root))
    assert collect_concepts(builder.ast, builder.trace) == set()
    node = builder.ast.get(2)
    assert node is not None
    node["resolved_declaration_id"] = 5
    assert collect_concepts(builder.ast, builder.trace) == {"program_function_call"}


def test_alternative_conditions_are_scoped_to_each_activation() -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "if_statement",
            branches=[
                ast_node(2, "condition_branch", condition=ast_node(3, "identifier")),
                ast_node(4, "condition_branch", condition=ast_node(5, "identifier")),
            ],
            elseBranch=ast_node(6, "compound_statement", statements=[]),
        )
    )
    branch = builder.construct(1, kind="compound.alternative")
    first = builder.action(3, branch, role="first_cond", kind="inline.condition")
    second = builder.action(5, branch, role="next_cond", kind="inline.condition")
    builder.act(branch.begin_action())
    builder.act(first)
    builder.act(branch.end_action())
    builder.act(branch.begin_action())
    builder.act(second)
    assert "alternative_conditions_in_order" not in collect_skills(
        builder.ast, builder.trace
    )
    builder.act(first)
    builder.act(builder.action(6, branch, role="else_branch", kind="compound"))
    skills = collect_skills(builder.ast, builder.trace)
    assert {"alternative_conditions_in_order", "alternative_single_branch"} <= skills


@pytest.mark.parametrize("preorder", [False, True])
@pytest.mark.parametrize("opaque_entry", [False, True])
def test_containing_action_skill_respects_unfold_order(
    preorder: bool, opaque_entry: bool
) -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "program_entry_point",
            body=[
                ast_node(
                    2,
                    "compound_statement",
                    statements=[ast_node(3, "assignment_statement")],
                ),
                ast_node(4, "assignment_statement"),
            ],
        )
    )
    root = builder.construct(1, kind="compound.sequence.program")
    nested = builder.construct(2, parent=root, preorder=preorder)
    nested.begin_action().rule.opaque = opaque_entry
    containing = builder.action(2, root, kind="compound")
    if not preorder:
        builder.act(containing)
    builder.act(nested.begin_action(), unfolded_from=containing)
    builder.act(builder.action(3, nested))
    builder.act(nested.end_action())
    if preorder:
        builder.act(containing)
    builder.act(builder.action(4, root))
    skills = collect_skills(builder.ast, builder.trace)
    assert ("construct_entered_before_inner" in skills) is opaque_entry
    assert "inner_construct_finished_before_next" in skills
    assert ("containing_action_before_inner" in skills) is (
        opaque_entry and not preorder
    )


@pytest.mark.parametrize(
    "node_type", ["break_statement", "continue_statement", "return_statement"]
)
def test_interruption_skill_requires_an_exit(node_type: str) -> None:
    builder = TraceBuilder(
        ast_node(
            1,
            "while_loop",
            body=ast_node(
                2,
                "compound_statement",
                statements=[
                    ast_node(3, node_type),
                ],
            ),
        )
    )
    loop = builder.construct(1, kind="compound.loop")
    builder.act(loop.begin_action())
    builder.act(builder.action(3, loop))
    assert "interruption_exits_constructs" not in collect_skills(
        builder.ast, builder.trace
    )
    builder.act(loop.end_action())
    assert "interruption_exits_constructs" in collect_skills(builder.ast, builder.trace)


def test_no_early_exit_requires_an_interruption_constrained_exit() -> None:
    builder = TraceBuilder(
        ast_node(
            1, "compound_statement", statements=[ast_node(2, "assignment_statement")]
        )
    )
    block = builder.construct(1)
    action = builder.action(2, block)
    builder.act(block.begin_action())
    builder.act(action)
    assert "no_early_exit_without_interruption" not in collect_skills(
        builder.ast, builder.trace
    )
    block.rule.transitions.append(
        TransitionDeclaration(
            "item",
            "END",
            constraints=ConstraintsDeclaration(
                interruption_mode=InterruptionType.BREAK
            ),
        )
    )
    assert "no_early_exit_without_interruption" in collect_skills(
        builder.ast, builder.trace
    )
    action.effects = EffectDeclaration(interruption_start=InterruptionType.BREAK)
    assert "no_early_exit_without_interruption" not in collect_skills(
        builder.ast, builder.trace
    )


def test_completion_marker_is_not_collected_as_a_skill() -> None:
    builder = TraceBuilder(ast_node(1, "program_entry_point", body=[]))
    root = builder.construct(
        1, name="global_statements_structure", kind="compound.sequence.program"
    )
    builder.act(root.begin_action())
    assert not is_everything_evaluated(builder.ast, builder.trace)
    builder.act(root.end_action())
    assert is_everything_evaluated(builder.ast, builder.trace)
    assert "everything_evaluated" not in collect_skills(builder.ast, builder.trace)
