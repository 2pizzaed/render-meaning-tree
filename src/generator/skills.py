from src.helpers.bitflags import bit

# Идентификаторы skill из domain/main.tpg в порядке первого появления.
SKILLS: dict[str, int] = {
    "correct_answer": bit(0),
    "interruption_not_considered": bit(1),
    "condition_value_not_considered": bit(2),
    "actions_order_violated": bit(3),
    "construct_not_closed": bit(4),
    "construct_not_entered": bit(5),
    "intermediate_action_skipped": bit(6),
    "action_already_passed": bit(7),
    "actions_skipped": bit(8),
    "no_transition": bit(9),
    "everything_evaluated": bit(10),
    "function_not_entered": bit(11),
    "function_already_exited": bit(12),
    "action_cannot_repeat": bit(13),
}

# Только skill у conclude: error/false, независимо от текста объяснения.
ERRORNEOUS_SKILLS: set[str] = {
    "interruption_not_considered",
    "condition_value_not_considered",
    "actions_order_violated",
    "construct_not_closed",
    "construct_not_entered",
    "intermediate_action_skipped",
    "action_already_passed",
    "actions_skipped",
    "no_transition",
    "function_not_entered",
    "function_already_exited",
    "action_cannot_repeat",
}
