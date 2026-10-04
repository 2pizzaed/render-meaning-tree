from src.helpers.bitflags import bit

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

