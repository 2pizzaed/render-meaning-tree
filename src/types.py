from typing import Literal, Dict, Any


NodeType = Literal[
    "program_entry_point",
    "if_statement",
    "while_loop",
    "range_for_loop",
    "compound_statement",
    "add_operator",
    "sub_operator",
    "mul_operator",
    "div_operator",
    "mod_operator",
    "floor_div_operator",
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
    "unary_operator",
    "unary_minus_operator",
    "unary_plus_operator",
    "unary_postfix_inc_operator",
    "unary_postfix_dec_operator",
    "unary_prefix_inc_operator",
    "unary_prefix_dec_operator",
    "identifier",
    "int_literal",
    "assignment_statement",
    "condition_branch",
]

NodeField = Literal["id", "type"] | str

Node = Dict[NodeField, Any]
