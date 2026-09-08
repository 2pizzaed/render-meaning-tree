from __future__ import annotations

from typing import cast

import pytest

from src.ast_managers import ASTNodeManager, CodeManager, NodePathElement
from src.coderenderer.entities import Token
from src.types import Node, SourceMap


def _path(
    node_id: int,
    node_type: str,
    parent: NodePathElement | None = None,
) -> NodePathElement:
    return NodePathElement(
        parent=parent,
        id=node_id,
        type=node_type,
        field_name=None,
        field_type="plain",
        container_field_id=None,
    )


def _manager(
    paths: list[NodePathElement],
    tokens: list[Token],
) -> CodeManager:
    ast = object.__new__(ASTNodeManager)
    ast._cache = {
        path.id: (
            path,
            cast(Node, {"id": path.id, "type": path.type}),
        )
        for path in paths
    }
    manager = object.__new__(CodeManager)
    manager._ast = ast
    # These tests construct a deliberately partial manager without invoking its
    # source-map-dependent methods.
    manager._source_map = cast(SourceMap, {})
    manager._tokens = tokens
    manager._code = ""
    manager._declarations = {"functions": [], "classes": [], "globals": []}
    manager._last_stream = None
    return manager


def _processed_ast_manager(root: Node) -> ASTNodeManager:
    manager = object.__new__(ASTNodeManager)
    manager._root = root
    manager._cache = {}
    manager._process()
    return manager


def _token(index: int, value: str, ast_node: NodePathElement | None) -> Token:
    return Token(index, value, "unknown", "unknown", index, ast_node)


@pytest.mark.parametrize(
    ("main_class_field", "entry_point_field"),
    [
        ("main_class_ref", "entry_point_node_ref"),
        ("main_class", "entry_point_node"),
    ],
)
def test_program_entry_point_reference_payloads_are_not_indexed(
    main_class_field: str,
    entry_point_field: str,
) -> None:
    repeated_statement = {"id": 2, "type": "return_statement"}
    root = cast(
        Node,
        {
            "id": 1,
            "type": "program_entry_point",
            "body": [repeated_statement],
            "main_class_id": 3,
            main_class_field: {
                "id": 3,
                "type": "class_definition",
                "body": {
                    "id": 4,
                    "type": "compound_statement",
                    "statements": [repeated_statement],
                },
            },
            "entry_point_node_id": 5,
            entry_point_field: {
                "id": 5,
                "type": "function_definition",
                "body": {
                    "id": 6,
                    "type": "compound_statement",
                    "statements": [repeated_statement],
                },
            },
        },
    )

    manager = _processed_ast_manager(root)

    assert set(manager._cache) == {1, 2}
    assert manager.get_path(2) == NodePathElement(
        parent=manager.get_path(1),
        id=2,
        type="return_statement",
        field_name="body",
        field_type="collection",
        container_field_id=0,
    )
    assert manager.get_path(3) is None
    assert manager.get_path(5) is None


def test_ref_suffix_is_not_indexed_on_other_node_types() -> None:
    root = cast(
        Node,
        {
            "id": 1,
            "type": "method_declaration",
            "owner_ref": {"id": 2, "type": "user_type"},
            "name": {"id": 3, "type": "identifier"},
        },
    )

    manager = _processed_ast_manager(root)

    assert set(manager._cache) == {1, 3}
    assert manager.get_path(2) is None


def test_line_number_to_ast_node_returns_least_nested_node_starting_on_line() -> None:
    root = _path(1, "program_entry_point")
    statement = _path(2, "assignment_statement", root)
    expression = _path(3, "binary_expression", statement)
    next_statement = _path(4, "return_statement", root)
    manager = _manager(
        [root, statement, expression, next_statement],
        [
            _token(0, "x", expression),
            _token(1, "\n", None),
            _token(2, "return", next_statement),
        ],
    )

    assert manager.line_number_to_ast_node(1) is statement
    assert manager.line_number_to_ast_node(2) is next_statement


def test_line_number_to_ast_node_returns_none_for_ambiguous_least_depth() -> None:
    root = _path(1, "program_entry_point")
    left_statement = _path(2, "assignment_statement", root)
    right_statement = _path(3, "assignment_statement", root)
    manager = _manager(
        [root, left_statement, right_statement],
        [
            _token(0, "x", left_statement),
            _token(1, ";", None),
            _token(2, "y", right_statement),
        ],
    )

    assert manager.line_number_to_ast_node(1) is None


def test_line_number_to_ast_node_returns_none_for_invalid_or_empty_line() -> None:
    root = _path(1, "program_entry_point")
    statement = _path(2, "assignment_statement", root)
    manager = _manager(
        [root, statement],
        [_token(0, "x", statement)],
    )

    assert manager.line_number_to_ast_node(0) is None
    assert manager.line_number_to_ast_node(2) is None


def test_line_number_to_ast_nodes_returns_all_nodes_starting_on_line_in_stable_order() -> (
    None
):
    root = _path(1, "program_entry_point")
    statement = _path(2, "assignment_statement", root)
    expression = _path(3, "binary_expression", statement)
    nested = _path(4, "identifier", expression)
    next_statement = _path(5, "return_statement", root)
    manager = _manager(
        [root, statement, expression, nested, next_statement],
        [
            _token(0, "x", nested),
            _token(1, "\n", None),
            _token(2, "return", next_statement),
        ],
    )

    assert manager.line_number_to_ast_nodes(1) == [statement, expression, nested]
    assert manager.line_number_to_ast_nodes(2) == [next_statement]
    assert manager.line_number_to_ast_nodes(0) == []


def test_ast_node_manager_finds_paths_and_nodes_by_exact_type() -> None:
    root = _path(1, "program_entry_point")
    first_statement = _path(2, "assignment_statement", root)
    expression = _path(3, "binary_expression", first_statement)
    second_statement = _path(4, "assignment_statement", root)
    manager = _manager(
        [root, first_statement, expression, second_statement],
        [],
    )

    assert manager.ast.find_paths_by_type("assignment_statement") == [
        first_statement,
        second_statement,
    ]
    assert manager.ast.find_paths_by_type("missing") == []
