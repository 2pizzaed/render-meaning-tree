from typing import List, Any
from dataclasses import dataclass

from src.types import Node
from src.serializers.types import StatementFact, CompPrehensionQuestion
from src.serializers.serializer import Serializer


s = Serializer()


def serialize(node: Node) -> CompPrehensionQuestion:
    return CompPrehensionQuestion(
        type="",  # TODO
        name="",  # TODO
        statement_facts=s.serialize(node),
    )


@s.node(type="program_entry_point")
def program_entry_point(node: Node) -> List[StatementFact]:
    children = node["body"]

    stmt_facts = [StatementFact(node, "parent_of", child) for child in children]

    stmt_facts += [
        StatementFact(sub, "next_sibling", obj)
        for sub, obj in zip(children, children[1:])
    ]

    stmt_facts += flatten([s.serialize(child) for child in children])

    return stmt_facts


@s.node(type="compound_statement")
def compound_stmt(node: Node) -> List[StatementFact]:
    children = node["statements"]

    stmt_facts = [StatementFact(node, "parent_of", child) for child in children]

    stmt_facts += [
        StatementFact(sub, "next_sibling", obj)
        for sub, obj in zip(children, children[1:])
    ]

    stmt_facts += flatten([s.serialize(child) for child in children])

    return stmt_facts


@s.node(type="if_statement")
def if_stmt(node: Node) -> List[StatementFact]:
    branches = node["branches"]

    stmt_facts = [StatementFact(node, "branches_item", branch) for branch in branches]

    stmt_facts += flatten([s.serialize(child) for child in branches])

    return stmt_facts


@s.node(type="condition_branch")
def cond_branch(node: Node) -> List[StatementFact]:
    return []


@s.nodes(
    types=[
        "add_operator",
        "sub_operator",
        "div_operator",
        "mul_operator",
        "floor_div_operator",
        "mod_operator",
        "pow_operator",
        "eq_operator",
        "ge_operator",
        "gt_operator",
        "le_operator",
        "lt_operator",
        "not_eq_operator",
        "reference_eq_operator",
        "short_circuit_and_operator",
        "short_circuit_or_operator",
    ]
)
def binary_op(node: Node) -> List[StatementFact]:
    return s.serialize(node["left_operand"]) + s.serialize(node["right_operand"])


@s.nodes(
    types=[
        "unary_operator",
        "unary_minus_operator",
        "unary_plus_operator",
        "unary_postfix_dec_operator",
        "unary_postfix_inc_operator",
        "unary_prefix_dec_operator",
        "unary_prefix_inc_operator",
    ]
)
def unary_op(node: Node) -> List[StatementFact]:
    return s.serialize(node["operand"])


@s.node(type="identifier")
def identifier(node: Node) -> List[StatementFact]:
    return []


@s.node(type="int_literal")
def int_literal(node: Node) -> List[StatementFact]:
    return []


@s.node(type="assignment_statement")
def assignment_stmt(node: Node) -> List[StatementFact]:
    return s.serialize(node["target"]) + s.serialize(node["value"])


@s.node(type="range_for_loop")
def for_stmt(node: Node) -> List[StatementFact]:
    # TODO: init statement fact?
    stmt_facts = [StatementFact(node, "body", node["body"])]

    stmt_facts += flatten([s.serialize(stmt) for stmt in node["body"]])

    return stmt_facts


@s.node(type="while_loop")
def while_statement(node: Node) -> List[StatementFact]:
    cond, body = node["condition"], node["body"]

    stmt_facts = [StatementFact(node, "cond", cond), StatementFact(node, "body", body)]

    stmt_facts += flatten(s.serialize(cond) + s.serialize(body))

    return stmt_facts


def flatten(lst: List[Any]) -> List[Any]:
    result = []

    for elem in lst:
        if isinstance(elem, list):
            result += flatten(elem)
        else:
            result.append(elem)

    return result
