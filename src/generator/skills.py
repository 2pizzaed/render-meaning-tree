from src.helpers.bitflags import bit

# Идентификаторы skill из domain/main.tpg в порядке первого появления.
# Skill — умение студента: правильный исход проверки засчитывает его, ошибочный — нарушает.
SKILLS: dict[str, int] = {
    "interruption_exits_constructs": bit(0),
    "condition_value_selects_next": bit(1),
    "construct_entered_before_inner": bit(2),
    "inner_construct_finished_before_next": bit(3),
    "passed_action_repeat": bit(4),
    "containing_action_before_inner": bit(5),
    "alternative_single_branch": bit(6),
    "alternative_conditions_in_order": bit(7),
    "actions_in_order": bit(8),
    "no_early_exit_without_interruption": bit(9),
    # Метка завершения программы (conclude: true), а не умение.
    "everything_evaluated": bit(10),
    "function_body_runs_on_call": bit(11),
    "function_not_resumed_after_exit": bit(12),
}

# Умения, которые может нарушить ошибочный ответ (skill у conclude: error).
ERRORNEOUS_SKILLS: set[str] = {
    "interruption_exits_constructs",
    "condition_value_selects_next",
    "construct_entered_before_inner",
    "inner_construct_finished_before_next",
    "passed_action_repeat",
    "containing_action_before_inner",
    "alternative_single_branch",
    "alternative_conditions_in_order",
    "actions_in_order",
    "no_early_exit_without_interruption",
    "function_body_runs_on_call",
    "function_not_resumed_after_exit",
}
