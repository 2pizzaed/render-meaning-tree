from typing import Literal

type NodeType = Literal[
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

type NodeField = Literal["id", "type"] | str

type TreeField = Literal["type", "unique_hash", "labels", "root_node"]

type TokenField = Literal["id", "value", "token_type", "byte_pos"] | str

type MapField = Literal[
        "type", "origin", "source_code", "language",
        "byte_positions", "declarations",
        "imports", "user_type_hierarchy"]

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]

type JsonObject = dict[str, JsonValue]

type JsonArray = list[JsonValue]

type JSON = JsonObject

type MeaningTree = dict[TreeField, JsonValue]

type Node = dict[NodeField, JsonValue]

type Token = dict[TokenField, JsonValue]

type SourceMap = dict[MapField, JsonValue]

type TokenList = dict[Literal["type", "tokens"], list[Token] | JsonValue]
