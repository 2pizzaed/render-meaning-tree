from src.json_property_path import ResolvedJSONPath
from src.model.rules import (
    ActionDeclaration,
    CallStackAction,
    ConstructDeclaration,
    EffectDeclaration,
    Identification,
    InterruptionType,
    TransitionDeclaration,
    load_construct_declarations_from_dict,
    locate_construct_declaration_by_ast_node,
)
from src.types import JSON


def test_identification_resolve_json_ignores_parent_origin_for_property_path():
    data: JSON = {
        "root": {
            "body": [
                {"type": "first"},
                {"type": "second"},
            ]
        }
    }
    identification = Identification(origin="parent", property_path="body / [0]")

    resolved = identification.resolve_json(data, current_path=("root",))

    assert resolved == ResolvedJSONPath(path=("root", "body", 0), value=data["root"]["body"][0]) # type: ignore


def test_identification_resolve_json_supports_previous_origin_with_next_navigation():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(origin="previous", property_path="^ / [next] / condition")

    resolved = identification.resolve_json(data, previous_path=("branches", 0, "condition"))

    assert resolved == ResolvedJSONPath(path=("branches", 1, "condition"), value=data["branches"][1]["condition"]) # type: ignore


def test_identification_get_from_json_supports_direct_property_lookup():
    data: JSON = {
        "program": {
            "elseBranch": {"type": "compound_statement"}
        }
    }
    identification = Identification(origin="parent", property="elseBranch")

    value = identification.get_from_json(data, current_path=("program", "condition"))

    assert value == {"type": "compound_statement"}


def test_identification_resolve_json_supports_role_in_list_from_parent():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(origin="parent", role_in_list="first_in_list")

    resolved = identification.resolve_json(data, current_path=("branches", 1))

    assert resolved == ResolvedJSONPath(path=("branches", 0), value=data["branches"][0]) # type: ignore


def test_identification_resolve_json_supports_role_in_list_next_from_previous():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(role_in_list="next_in_list")

    resolved = identification.resolve_json(
        data,
        current_path=("branches",),
        previous_path=("branches", 0),
    )

    assert resolved == ResolvedJSONPath(path=("branches", 1), value=data["branches"][1]) # type: ignore


def test_transition_declaration_loads_single_effect_from_legacy_list():
    transition = TransitionDeclaration.from_dict(
        {
            "from": "body",
            "to": "END",
            "effects": [
                {"interruption_stop": "return"},
                {"call_stack": "drop_frame"},
            ],
        }
    )

    assert transition.effects is not None
    assert transition.effects.interruption_stop is InterruptionType.RETURN
    assert transition.effects.call_stack is CallStackAction.DROP_FRAME


def test_action_declaration_knows_parent_construct_declaration():
    action = ActionDeclaration(role="body", kind="inline")
    construct = ConstructDeclaration(
        name="demo",
        kind="compound",
        ast_node="demo_node",
        actions=[action],
    )

    assert action.parent is construct


def test_action_declaration_loads_explicit_opaque_flag():
    action = ActionDeclaration.from_dict(
        {"role": "name", "kind": "identifier", "opaque": False}
    )

    assert action.opaque is False
    assert not action.is_opaque


def test_construct_declaration_from_dict_adds_missing_boundary_actions():
    construct = ConstructDeclaration.from_dict(
        "demo",
        {
            "kind": "compound",
            "ast_node": "demo_node",
            "actions": [
                {"role": "body", "kind": "inline"},
            ],
        },
    )

    assert [(action.role, action.kind) for action in construct.actions] == [
        ("BEGIN", "BEGIN"),
        ("body", "inline"),
        ("END", "END"),
    ]
    assert all(action.parent is construct for action in construct.actions)


def test_construct_declaration_from_dict_keeps_explicit_boundary_actions():
    construct = ConstructDeclaration.from_dict(
        "demo",
        {
            "kind": "compound",
            "ast_node": "demo_node",
            "actions": [
                {"role": "BEGIN", "kind": "custom.begin"},
                {"role": "body", "kind": "inline"},
                {"role": "END", "kind": "custom.end"},
            ],
        },
    )

    assert [(action.role, action.kind) for action in construct.actions] == [
        ("BEGIN", "custom.begin"),
        ("body", "inline"),
        ("END", "custom.end"),
    ]


def test_construct_declaration_compiled_transitions_expand_generalization():
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

    compiled = construct.compiled_transitions()

    assert [(transition.from_role, transition.to_role) for transition in compiled] == [
        ("BEGIN", "first"),
        ("first", "next"),
        ("next", "next"),
    ]
    assert all(transition.from_role != "item" for transition in compiled)


def test_construct_declaration_compiled_transition_search_supports_generalization():
    construct = ConstructDeclaration(
        name="sequence",
        kind="compound",
        ast_node="sequence_node",
        actions=[
            ActionDeclaration(role="first", kind="inline", generalization="item"),
            ActionDeclaration(role="next", kind="inline", generalization="item"),
        ],
        transitions=[TransitionDeclaration(from_role="item", to_role="next")],
    )

    concrete = construct.compiled_transitions_from_role("first")
    generalized = construct.compiled_transitions_from_role("item")

    assert [transition.from_role for transition in concrete] == ["first"]
    assert [transition.from_role for transition in generalized] == ["first", "next"]


def test_construct_declaration_compiled_transitions_merge_effects_without_overwriting_transition_effect():
    construct_effect = EffectDeclaration(
        interruption_start=InterruptionType.BREAK,
        interruption_stop=InterruptionType.CONTINUE,
    )
    action_effect = EffectDeclaration(
        interruption_stop=InterruptionType.RETURN,
        call_stack=CallStackAction.ADD_FRAME,
    )
    transition_effect = EffectDeclaration(interruption_start=InterruptionType.NONE)
    construct = ConstructDeclaration(
        name="loop",
        kind="compound",
        ast_node="loop_node",
        effects=construct_effect,
        actions=[
            ActionDeclaration(role="BEGIN", kind="BEGIN", effects=action_effect),
            ActionDeclaration(role="body", kind="inline"),
        ],
        transitions=[
            TransitionDeclaration(from_role="BEGIN", to_role="END", effects=transition_effect),
            TransitionDeclaration(from_role="END", to_role="BEGIN", effects=transition_effect),
        ],
    )

    begin_transition, end_transition = construct.compiled_transitions()

    assert begin_transition.effects is not None
    assert begin_transition.effects.interruption_start is InterruptionType.NONE
    assert begin_transition.effects.interruption_stop is InterruptionType.RETURN
    assert begin_transition.effects.call_stack is CallStackAction.ADD_FRAME

    assert end_transition.effects is not None
    assert end_transition.effects.interruption_start is InterruptionType.NONE
    assert end_transition.effects.interruption_stop is None
    assert end_transition.effects.call_stack is None


def test_construct_declaration_compiled_transitions_merge_action_effect_into_all_outgoing_transitions():
    action_effect = EffectDeclaration(interruption_stop=InterruptionType.RETURN)
    construct = ConstructDeclaration(
        name="call",
        kind="compound",
        ast_node="call_node",
        actions=[
            ActionDeclaration(role="func", kind="compound", effects=action_effect),
            ActionDeclaration(role="END", kind="END"),
        ],
        transitions=[
            TransitionDeclaration(from_role="func", to_role="END"),
            TransitionDeclaration(from_role="func", to_role="END", constraints=None),
        ],
    )

    compiled = construct.compiled_transitions()

    assert len(compiled) == 2
    assert all(transition.effects is not None for transition in compiled)
    assert all(transition.effects.interruption_stop is InterruptionType.RETURN for transition in compiled if transition.effects)


def test_construct_declaration_compiled_transitions_do_not_mutate_original_declarations():
    action_effect = EffectDeclaration(call_stack=CallStackAction.ADD_FRAME)
    construct = ConstructDeclaration(
        name="sequence",
        kind="compound",
        ast_node="sequence_node",
        actions=[
            ActionDeclaration(role="first", kind="inline", generalization="item", effects=action_effect),
            ActionDeclaration(role="next", kind="inline", generalization="item"),
        ],
        transitions=[
            TransitionDeclaration(from_role="item", to_role="next", to_when_absent=["END"]),
        ],
    )

    compiled = construct.compiled_transitions()
    compiled[0].to_when_absent.append("first")  # type: ignore[union-attr]
    compiled[0].effects.call_stack = CallStackAction.DROP_FRAME  # type: ignore[union-attr]

    assert construct.transitions[0].from_role == "item"
    assert construct.transitions[0].effects is None
    assert construct.transitions[0].to_when_absent == ["END"]
    assert action_effect.call_stack is CallStackAction.ADD_FRAME


def test_construct_declaration_ast_node_query_matches_node_conditions():
    construct = ConstructDeclaration(
        name="program_with_body",
        kind="compound.sequence.program",
        ast_node={
            "query": [
                {"type": "program_entry_point", "exists": "body / [0]"},
                {
                    "type": "program_entry_point",
                    "equals": {"path": "body / [0] / type", "value": "int_literal"},
                },
                {"type": "program_entry_point", "length": {"path": "body", "equals": 1}},
                {"type": "program_entry_point", "contains": {"path": "tags", "value": "entry"}},
            ],
        },
    )

    assert construct.matches_ast_node(
        {
            "type": "program_entry_point",
            "body": [{"type": "int_literal"}],
            "tags": ["entry"],
        }
    )
    assert not construct.matches_ast_node(
        {
            "type": "program_entry_point",
            "body": [{"type": "identifier"}],
            "tags": ["entry"],
        }
    )


def test_construct_declaration_ast_node_query_supports_contains_any():
    construct = ConstructDeclaration(
        name="inline_compound_atom",
        kind="inline",
        ast_node={
            "query": [
                {
                    "type": ["assignment_statement", "expression_statement"],
                    "contains_any": {"key": "type", "value_in": ["function_call", "method_call"]},
                }
            ],
        },
    )

    assert construct.matches_ast_node(
        {
            "type": "assignment_statement",
            "left": {"type": "identifier"},
            "right": {
                "type": "function_call",
                "function": {"type": "identifier", "name": "f"},
            },
        }
    )
    assert not construct.matches_ast_node(
        {
            "type": "assignment_statement",
            "left": {"type": "identifier"},
            "right": {"type": "int_literal", "value": 1},
        }
    )

    logical_construct = ConstructDeclaration(
        name="inline_named_call_atom",
        kind="inline",
        ast_node={
            "query": [
                {
                    "type": "assignment_statement",
                    "contains_any": {
                        "and": [
                            {"key": "type", "value": "function_call"},
                            {"not": {"key": "name", "value": "ignored"}},
                        ]
                    },
                }
            ],
        },
    )
    assert logical_construct.matches_ast_node(
        {
            "type": "assignment_statement",
            "right": {"type": "function_call", "name": "used"},
        }
    )


def test_locate_construct_declaration_supports_ast_node_query():
    declarations = load_construct_declarations_from_dict(
        {
            "program": {
                "kind": "compound.sequence.program",
                "ast_node": {
                    "query": [{"type": "program_entry_point", "exists": "body / [0]"}],
                },
            },
            "empty_program": {
                "kind": "compound.sequence.program",
                "ast_node": {
                    "query": [{"type": "program_entry_point", "length": {"path": "body", "equals": 0}}],
                },
            },
        }
    )

    matched = locate_construct_declaration_by_ast_node(
        {"type": "program_entry_point", "body": [{"type": "identifier"}]},
        declarations,
    )

    assert matched is not None
    assert matched.name == "program"
    assert locate_construct_declaration_by_ast_node("program_entry_point", declarations) is None


def test_locate_construct_declaration_prefers_more_specific_ast_node_query():
    declarations = load_construct_declarations_from_dict(
        {
            "inline_atom": {
                "kind": "inline",
                "ast_node": ["assignment_statement", "expression_statement"],
            },
            "inline_compound_atom": {
                "kind": "inline",
                "ast_node": {
                    "query": [
                        {
                            "type": ["assignment_statement", "expression_statement"],
                            "contains_any": {"key": "type", "value": "function_call"},
                        }
                    ]
                },
            },
        }
    )

    matched = locate_construct_declaration_by_ast_node(
        {
            "type": "assignment_statement",
            "right": {"type": "function_call"},
        },
        declarations,
    )

    assert matched is not None
    assert matched.name == "inline_compound_atom"


def test_load_construct_declarations_from_dict_skips_shared_entries():
    declarations = load_construct_declarations_from_dict(
        {
            "inline_atom_ast_nodes": ["identifier", "assignment_statement"],
            "inline_atom": {
                "kind": "inline",
                "ast_node": ["identifier", "assignment_statement"],
            },
        }
    )

    assert [declaration.name for declaration in declarations] == ["inline_atom"]


def test_construct_declaration_ast_node_query_supports_logical_operators():
    construct = ConstructDeclaration(
        name="branching_control",
        kind="compound.branch",
        ast_node={
            "query": [
                {
                    "or": [
                        {"type": "if_statement", "exists": "branches / [0]"},
                        {"type": "while_loop", "exists": "condition"},
                    ]
                },
                {
                    "not": {
                        "type": "while_loop",
                        "length": {"path": "body / statements", "equals": 0},
                    }
                },
            ]
        },
    )

    assert construct.matches_ast_node(
        {
            "type": "if_statement",
            "branches": [{"condition": {"type": "identifier"}}],
        }
    )
    assert not construct.matches_ast_node(
        {
            "type": "while_loop",
            "condition": {"type": "identifier"},
            "body": {"statements": []},
        }
    )


def test_construct_declaration_ast_node_query_rejects_multiple_checks_in_one_item():
    try:
        ConstructDeclaration(
            name="ambiguous_predicate",
            kind="inline",
            ast_node={
                "query": [
                    {
                        "type": "identifier",
                        "exists": "name",
                        "contains": {"path": "tags", "value": "entry"},
                    }
                ]
            },
        )
    except ValueError as error:
        assert "at most one check operator" in str(error)
    else:
        raise AssertionError("Multiple ast_node checks in one query item should fail")


def test_construct_declarations_reject_duplicate_ast_node_predicates():
    data = {
        "first": {
            "kind": "inline",
            "ast_node": ["identifier", "int_literal"],
        },
        "second": {
            "kind": "inline",
            "ast_node": "identifier",
        },
    }

    try:
        load_construct_declarations_from_dict(data)
    except ValueError as error:
        assert "Duplicate ast_node predicate" in str(error)
    else:
        raise AssertionError("Duplicate ast_node predicate should fail")


def test_construct_declarations_reject_duplicate_shorthand_and_single_query_predicate():
    data = {
        "first": {
            "kind": "inline",
            "ast_node": "identifier",
        },
        "second": {
            "kind": "inline",
            "ast_node": {"query": [{"type": "identifier"}]},
        },
    }

    try:
        load_construct_declarations_from_dict(data)
    except ValueError as error:
        assert "Duplicate ast_node predicate" in str(error)
    else:
        raise AssertionError("Duplicate ast_node predicate should fail")
