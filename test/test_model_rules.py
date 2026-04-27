from src.json_property_path import ResolvedJSONPath
from src.model.rules import (
    ActionDeclaration,
    CallStackAction,
    ConstructDeclaration,
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
