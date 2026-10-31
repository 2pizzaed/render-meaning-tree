"""Порядок вычисления вызовов внутри выражения.

Строгая цепочка — порядок по умолчанию: аргумент раньше вызова (`f(g(x))`),
операнды слева направо. В C++ оператор с нестрогим порядком операндов
(сложение, индекс и прочие бинарные, кроме `&&`, `||` и присваивания) становится
группой `eval_unordered_structure`, если каждый операнд сводится к одному шагу.
Присваивание упорядочено языком: в Java сначала левая часть, в Python и C++17
сначала правая.
"""

from __future__ import annotations

from typing import cast

from src.types import Node

_CALL_TYPES = frozenset({"function_call", "method_call"})
_ASSIGNMENT_TYPES = frozenset({"assignment_statement", "assignment_expression"})
# Операнды вычисляются в указанном порядке, а не свободно.
_SEQUENCED_TYPES = _ASSIGNMENT_TYPES | {
    "short_circuit_and_operator",
    "short_circuit_or_operator",
}
_SKIP_CHILD_KEYS = frozenset({"id", "type", "unique_hash"})


def collect_steps(node: Node, language: str) -> list[Node]:
    """Шаги строгой цепочки: вызовы и якоря неупорядоченных групп."""
    node_type = node.get("type")
    if node_type in _CALL_TYPES:
        callee = [_as_node(node.get("object")), _as_node(node.get("function"))]
        children = [child for child in callee if child is not None]
        return [*_concat(children + _node_list(node.get("arguments")), language), node]

    operands = _operands(node)
    if operands is None:
        return _concat(_child_nodes(node), language)
    if node_type in _ASSIGNMENT_TYPES:
        return _concat(operands if language == "java" else operands[::-1], language)
    operand_steps = [collect_steps(operand, language) for operand in operands]
    if _forms_group(node, operand_steps, language):
        return [node]
    return [step for steps in operand_steps for step in steps]


def steps_of(node: Node, language: str) -> list[Node]:
    """Шаги, которые конструкт на этом узле раскладывает в свои действия."""
    members = unordered_member_steps(node, language)
    return members if members is not None else collect_steps(node, language)


def unordered_member_steps(node: Node, language: str) -> list[Node] | None:
    """Шаги группы со свободным порядком либо None, если узел — не такая группа.

    Вложенная группа (`(f(1) + f(2)) + f(3)`) раскрывается в своих участников:
    вычисления операндов не упорядочены, поэтому `f(3)` может оказаться и между
    `f(1)` и `f(2)`.
    """
    operands = _operands(node)
    if operands is None:
        return None
    operand_steps = [collect_steps(operand, language) for operand in operands]
    if not _forms_group(node, operand_steps, language):
        return None
    members: list[Node] = []
    for (step,) in operand_steps:
        nested = unordered_member_steps(step, language)
        members.extend(nested if nested is not None else [step])
    return members


def _forms_group(node: Node, operand_steps: list[list[Node]], language: str) -> bool:
    """Группа строится только когда каждый операнд даёт ровно один шаг.

    Иначе внутренний порядок (например, `g` раньше `f` в `f(g(x)) + h(y)`)
    сохраняется строгой цепочкой.
    """
    return (
        language == "c++"
        and node.get("type") not in _SEQUENCED_TYPES
        and all(len(steps) == 1 for steps in operand_steps)
    )


def _operands(node: Node) -> list[Node] | None:
    """Операнды в порядке записи: стороны бинарного оператора, присваивания или индекса."""
    node_type = node.get("type")
    if node_type == "index_expression":
        keys = ("expr", "index")
    elif node_type in _ASSIGNMENT_TYPES and "target" in node:
        keys = ("target", "value")
    else:
        keys = ("left_operand", "right_operand")
    operands = [_as_node(node.get(key)) for key in keys]
    if any(operand is None for operand in operands):
        return None
    return cast(list[Node], operands)


def _concat(nodes: list[Node], language: str) -> list[Node]:
    return [step for child in nodes for step in collect_steps(child, language)]


def _child_nodes(node: Node) -> list[Node]:
    children: list[Node] = []
    for key, value in node.items():
        if key in _SKIP_CHILD_KEYS:
            continue
        child = _as_node(value)
        if child is not None:
            children.append(child)
        else:
            children.extend(_node_list(value))
    return children


def _node_list(value: object) -> list[Node]:
    if not isinstance(value, list):
        return []
    return [node for item in value if (node := _as_node(item)) is not None]


def _as_node(value: object) -> Node | None:
    if isinstance(value, dict) and isinstance(value.get("type"), str):
        return cast(Node, value)
    return None
