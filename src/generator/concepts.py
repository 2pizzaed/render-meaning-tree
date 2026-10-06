"""Concepts participating in the supplied trace, at its available granularity."""

from collections.abc import Sequence

from src.ast_managers import ASTNodeManager
from src.generator.helpers.trace_features import (
    TracePredicate,
    active_node_paths,
    function_entries,
    has_node_types,
)
from src.generator.lookup import lookup_function_call_definition_by_ast_id
from src.helpers.bitflags import bit
from src.model.situation import TraceAct

# Словарь концепций (Concepts)
CONCEPTS: dict[str, int | dict[str, int]] = {
    # Expressions with flags
    "expressions": {
        "pointers": bit(0),
        "bitwise": bit(1),
        "member_access": bit(2),
        "arrays": bit(3),
        "type_casts": bit(4),
        "io": bit(5),
        "logical": bit(6),
        "arithmetic": bit(7),
        "ternary_conditions": bit(8),
        "lib_function_call": bit(9),
        "program_function_call": bit(10),
        # Plain statements with flags
        "var_declaration": bit(11),
        "assignment": bit(12),
        "delete": bit(16),
        "strings": bit(17),
        "list_collections": bit(18),
        "map_collections": bit(19),
        "object_new": bit(20),
    },
    # Structures with flags and invisible
    "units": {
        "function": bit(21),
        "structure": bit(22),
        "interface": bit(23),
        "class": bit(24),
        "field": bit(25),
        "method": bit(26),
        "constructor": bit(27),
        "destructor": bit(28),
        "generic_type": bit(29),
        "return": bit(15),
    },
    # Loops with flags
    "loops": {
        "general_for_loop": bit(30),
        "range_for_loop": bit(31),
        "for_each_loop": bit(32),
        "while_loop": bit(33),
        "do_while_loop": bit(34),
        "infinite_loop": bit(35),
        "break": bit(13),
        "continue": bit(14),
    },
    # Branches with flags
    "branches": {
        "if": bit(36),
        "else": bit(37),
        "elseif": bit(38),
        "switch": bit(39),
        "fallthrough_case": bit(40),
        "default_case": bit(41),
    },
    "recursion": bit(42),
    "loop_iteration": bit(43),
    "call_depth": bit(44),
}


def has_pointers(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "pointer_type",
        "pointer_pack",
        "pointer_unpack",
        "pointer_member_access",
        "pointer_input_command",
    )


def has_bitwise(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "bitwise_and_operator",
        "bitwise_or_operator",
        "xor_operator",
        "inversion_operator",
        "left_shift_operator",
        "right_shift_operator",
    ) or _has_augmented_operator(
        ast,
        trace,
        {
            "bitwise_and",
            "bitwise_or",
            "bitwise_xor",
            "bitwise_shift_left",
            "bitwise_shift_right",
        },
    )


def has_member_access(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "member_access", "pointer_member_access")


def has_arrays(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "array_type",
        "array_literal",
        "array_initializer",
        "array_new_expression",
        "index_expression",
    )


def has_type_casts(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "cast_type_expression")


def has_io(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "format_input",
        "format_print",
        "pointer_input_command",
        "input_command",
        "print_values",
    )


def has_logical(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "short_circuit_and_operator",
        "short_circuit_or_operator",
        "long_circuit_and_operator",
        "long_circuit_or_operator",
        "not_operator",
    )


def has_arithmetic(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "add_operator",
        "sub_operator",
        "mul_operator",
        "div_operator",
        "mod_operator",
        "matrix_mul_operator",
        "floor_div_operator",
        "pow_operator",
        "unary_minus_operator",
        "unary_plus_operator",
        "unary_postfix_inc_operator",
        "unary_postfix_dec_operator",
        "unary_prefix_inc_operator",
        "unary_prefix_dec_operator",
    ) or _has_augmented_operator(
        ast,
        trace,
        {
            "add",
            "sub",
            "mul",
            "div",
            "floor_div",
            "mod",
            "pow",
        },
    )


def _has_augmented_operator(
    ast: ASTNodeManager, trace: Sequence[TraceAct], operators: set[str]
) -> bool:
    for path in active_node_paths(ast, trace):
        if path.type not in {"assignment_statement", "assignment_expression"}:
            continue
        node = ast.get(path.id)
        operator = node.get("augmented_operator") if node is not None else None
        if isinstance(operator, str) and operator in operators:
            return True
    return False


def has_ternary_conditions(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "ternary_operator")


def has_lib_function_call(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """Recognize semantic library calls; unresolved generic calls stay unclassified."""
    return has_io(ast, trace) or has_node_types(
        ast, trace, "memory_allocation_call", "memory_free_call"
    )


def has_program_function_call(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    for path in active_node_paths(ast, trace):
        if path.type not in {"function_call", "method_call"}:
            continue
        node = ast.get(path.id)
        declaration_id = (
            node.get("resolved_declaration_id") if node is not None else None
        )
        if isinstance(declaration_id, int):
            declaration = ast.get(declaration_id)
            if declaration is not None and declaration["type"] in {
                "function_declaration",
                "method_declaration",
                "function_definition",
                "method_definition",
            }:
                return True
            # A resolved external target must not fall back to a same-named local function.
            continue
        if any(
            act.action.parent.ast_id == path.id
            and "call" in act.action.parent.rule.kind_classes
            for act in trace
        ):
            return True
        if (
            trace
            and trace[0].situation.code.ast is ast
            and lookup_function_call_definition_by_ast_id(
                trace[0].situation.code, path.id
            )
            is not None
        ):
            return True
    return False


def has_var_declaration(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast, trace, "variable_declaration", "separated_variable_declaration"
    )


def has_assignment(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "assignment_statement",
        "assignment_expression",
        "multiple_assignment_statement",
        "chained_assignment_statement",
    )


def has_delete(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "delete_statement", "delete_expression")


def has_strings(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "string_type",
        "string_literal",
        "interpolated_string_literal",
        "string_format",
    )


def has_list_collections(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "list_type",
        "list_literal",
        "unmodifiable_list_type",
        "unmodifiable_list_literal",
    )


def has_map_collections(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "dictionary_type", "dictionary_literal")


def has_object_new(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "object_new_expression",
        "placement_new_expression",
        "constructor_call",
    )


def has_function(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "function_definition", "function_declaration")


def has_structure(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "structure_definition",
        "structure_declaration",
        "structure_type",
        "generic_structure_type",
    )


def has_interface(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "interface_definition",
        "interface_declaration",
        "interface_type",
        "generic_interface",
    )


def has_class(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "class_definition",
        "class_declaration",
        "class_type",
        "generic_class_type",
    )


def has_field(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "field_declaration")


def has_method(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast, trace, "method_definition", "method_declaration", "method_call"
    )


def has_constructor(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "object_constructor_definition",
        "object_constructor_declaration",
        "constructor_call",
    )


def has_destructor(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "object_destructor_definition",
        "object_destructor_declaration",
        "destructor_call",
    )


def has_generic_type(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(
        ast,
        trace,
        "generic_user_type",
        "generic_class_type",
        "generic_structure_type",
        "generic_interface",
    )


def has_return(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "return_statement")


def has_general_for_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "general_for_loop")


def has_range_for_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "range_for_loop")


def has_for_each_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "for_each_loop")


def has_while_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "while_loop", "while_else_loop")


def has_do_while_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "do_while_loop")


def has_infinite_loop(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """Recognize the AST construct, without claiming nontermination of a run."""
    return has_node_types(ast, trace, "infinite_loop")


def has_break(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "break_statement")


def has_continue(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "continue_statement")


def has_if(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "if_statement")


def has_else(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return any(
        path.parent is not None
        and path.parent.type == "if_statement"
        and path.field_name == "elseBranch"
        for path in active_node_paths(ast, trace)
    )


def has_elseif(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return any(
        path.type == "condition_branch"
        and path.field_name == "branches"
        and isinstance(path.container_field_id, int)
        and path.container_field_id > 0
        for path in active_node_paths(ast, trace)
    )


def has_switch(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "switch_statement")


def has_fallthrough_case(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "fallthrough_case_block")


def has_default_case(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return has_node_types(ast, trace, "default_case_block")


def has_recursion(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    return any(
        len({construct.ast_id for construct in stack}) < len(stack)
        for stack in function_entries(ast, trace)
    )


def has_loop_iteration(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """At least one loop body was entered, including an empty body."""
    return any(
        "loop" in act.action.parent.rule.kind_classes
        and act.action.rule.role == "body"
        and ast.exists(act.action.parent.ast_id)
        for act in trace
    )


def has_call_depth(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """At least two function bodies were active at the same time."""
    return any(len(stack) > 1 for stack in function_entries(ast, trace))


CONCEPT_PREDICATES: dict[str, TracePredicate] = {
    "pointers": has_pointers,
    "bitwise": has_bitwise,
    "member_access": has_member_access,
    "arrays": has_arrays,
    "type_casts": has_type_casts,
    "io": has_io,
    "logical": has_logical,
    "arithmetic": has_arithmetic,
    "ternary_conditions": has_ternary_conditions,
    "lib_function_call": has_lib_function_call,
    "program_function_call": has_program_function_call,
    "var_declaration": has_var_declaration,
    "assignment": has_assignment,
    "delete": has_delete,
    "strings": has_strings,
    "list_collections": has_list_collections,
    "map_collections": has_map_collections,
    "object_new": has_object_new,
    "function": has_function,
    "structure": has_structure,
    "interface": has_interface,
    "class": has_class,
    "field": has_field,
    "method": has_method,
    "constructor": has_constructor,
    "destructor": has_destructor,
    "generic_type": has_generic_type,
    "return": has_return,
    "general_for_loop": has_general_for_loop,
    "range_for_loop": has_range_for_loop,
    "for_each_loop": has_for_each_loop,
    "while_loop": has_while_loop,
    "do_while_loop": has_do_while_loop,
    "infinite_loop": has_infinite_loop,
    "break": has_break,
    "continue": has_continue,
    "if": has_if,
    "else": has_else,
    "elseif": has_elseif,
    "switch": has_switch,
    "fallthrough_case": has_fallthrough_case,
    "default_case": has_default_case,
    "recursion": has_recursion,
    "loop_iteration": has_loop_iteration,
    "call_depth": has_call_depth,
}


def collect_concepts(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> set[str]:
    """Collect participating concepts; a prefix describes only that prefix."""
    return {
        name for name, predicate in CONCEPT_PREDICATES.items() if predicate(ast, trace)
    }
