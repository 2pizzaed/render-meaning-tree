"""Порядок вызовов внутри выражения: строгая цепочка и группы C++."""

from __future__ import annotations

from src.generator.utilities import code_snippet_to_registry
from src.model.situation import Action, Construct
from src.types import Node


def _first_argument_id(node: Node) -> int:
    arguments = node.get("arguments")
    assert isinstance(arguments, list) and arguments
    first = arguments[0]
    assert isinstance(first, dict)
    argument_id = first.get("id")
    assert isinstance(argument_id, int)
    return argument_id


def _parent_type(construct: Construct, action: Action) -> str | None:
    if action.ast_id is None:
        return None
    parent = construct.owner.code.ast.get_parent_of(action.ast_id)
    if not isinstance(parent, dict):
        return None
    parent_type = parent.get("type")
    return parent_type if isinstance(parent_type, str) else None


def _contents(construct: Construct) -> list[Action]:
    return [action for action in construct.actions if action.rule.role == "content"]


def _groups(registry_constructs: dict[int, Construct]) -> list[Construct]:
    return [
        construct
        for construct in registry_constructs.values()
        if construct.rule.name == "eval_unordered_structure"
    ]


def test_python_addition_keeps_one_strict_chain() -> None:
    registry = code_snippet_to_registry(
        "def f(x):\n    return x\ny = f(1) + f(2)\n",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and _contents(construct)
    )
    contents = _contents(statement)
    assert [action.ast_node["type"] for action in contents if action.ast_node] == [
        "function_call",
        "function_call",
    ]
    assert all(action.rule.strict_order for action in contents)


def test_nested_call_is_inner_then_outer() -> None:
    registry = code_snippet_to_registry(
        "def f(x):\n    return x\ny = f(f(1))\n",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and len(_contents(construct)) == 2
    )
    inner, outer = _contents(statement)
    assert inner.ast_node is not None and outer.ast_node is not None
    assert inner.ast_id != outer.ast_id
    assert _first_argument_id(outer.ast_node) == inner.ast_id


def test_cpp_addition_is_an_unordered_group() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\nint main() { int y = f(1) + f(2); }\n",
        language="c++",
    )
    groups = _groups(registry.constructs)
    assert len(groups) == 1
    contents = _contents(groups[0])
    assert len(contents) == 2
    assert all(not action.rule.strict_order for action in contents)
    assert {action.ast_node["type"] for action in contents if action.ast_node} == {
        "function_call"
    }
    for action in contents:
        call = registry.get_construct_for(action.ast_id or -1)
        assert call is not None
        assert call.rule.name == "func_call_structure"
        assert call.parent is groups[0]


def test_cpp_nested_groups_merge_into_one() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\nint main() { int y = (f(1) + f(2)) + f(3); }\n",
        language="c++",
    )
    groups = _groups(registry.constructs)
    assert len(groups) == 1
    contents = _contents(groups[0])
    assert len(contents) == 3
    for action in contents:
        call = registry.get_construct_for(action.ast_id or -1)
        assert call is not None
        assert call.parent is groups[0]


def test_cpp_group_in_call_argument_belongs_to_the_statement() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\nint g(int x) { return x; }\n"
        "int main() { int y = f(g(1) + g(2)); }\n",
        language="c++",
    )
    groups = _groups(registry.constructs)
    assert len(groups) == 1
    statement = groups[0].parent
    assert statement is not None
    assert statement.rule.name == "inline_compound_atom_structure"
    assert _contents(statement)[0].ast_id == groups[0].ast_id


def test_cpp_nested_call_stays_before_the_outer_call() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\nint g(int x) { return x; }\n"
        "int main() { int y = f(g(1)); }\n",
        language="c++",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and len(_contents(construct)) == 2
    )
    inner, outer = _contents(statement)
    assert outer.ast_node is not None
    assert _first_argument_id(outer.ast_node) == inner.ast_id


def test_cpp_nested_operand_is_not_split_into_an_unordered_group() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\nint g(int x) { return x; }\n"
        "int h(int x) { return x; }\n"
        "int main() { int y = f(g(1)) + h(2); }\n",
        language="c++",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and len(_contents(construct)) == 3
    )
    first, second, third = _contents(statement)
    assert second.ast_node is not None and first.ast_id is not None
    assert _first_argument_id(second.ast_node) == first.ast_id
    assert third.ast_id != first.ast_id


def test_cpp_index_call_is_after_the_rhs_group() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\n"
        "int main() { int a[2]; a[f(1)] = f(2) + f(3); }\n",
        language="c++",
    )
    groups = _groups(registry.constructs)
    assert len(groups) == 1
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and any(action.ast_id == groups[0].ast_id for action in _contents(construct))
    )
    group_step, index_call = _contents(statement)
    assert group_step.ast_id == groups[0].ast_id
    assert index_call.ast_node is not None
    assert index_call.ast_node["type"] == "function_call"
    assert group_step.rule.strict_order and index_call.rule.strict_order
    rhs_calls = _contents(groups[0])
    assert len(rhs_calls) == 2
    assert index_call.ast_id not in {action.ast_id for action in rhs_calls}


def test_python_assignment_evaluates_rhs_before_index() -> None:
    registry = code_snippet_to_registry(
        "def f(x):\n    return x\na = [0]\na[f(1)] = f(2) + f(3)\n",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and len(_contents(construct)) == 3
    )
    first, second, index = _contents(statement)
    assert _parent_type(statement, first) == "add_operator"
    assert _parent_type(statement, second) == "add_operator"
    assert _parent_type(statement, index) == "index_expression"


def test_java_assignment_evaluates_index_before_rhs() -> None:
    registry = code_snippet_to_registry(
        "int f(int x) { return x; }\n"
        "void main() { int[] a = new int[2]; a[f(1)] = f(2); }\n",
        language="java",
    )
    assert _groups(registry.constructs) == []
    statement = next(
        construct
        for construct in registry.constructs.values()
        if construct.rule.name == "inline_compound_atom_structure"
        and len(_contents(construct)) == 2
    )
    index_call, rhs_call = _contents(statement)
    assert _parent_type(statement, index_call) == "index_expression"
    assert _parent_type(statement, rhs_call) == "assignment_statement"
