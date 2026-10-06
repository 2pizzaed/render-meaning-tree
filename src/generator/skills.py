"""Skills exercised by a trace, including skills labelled only on TPG errors.

These predicates describe participation, not student mastery or a replay of
CtrlFlow_check. The input trace and AST are read without advancing execution.
"""

from collections.abc import Iterator, Sequence

from src.ast_managers import ASTNodeManager
from src.generator.helpers.trace_features import (
    TracePredicate,
    construct_runs,
    is_function_construct,
    is_within,
)
from src.helpers.bitflags import bit
from src.model.rules import EffectDeclaration, InterruptionType
from src.model.situation import TraceAct

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


def _apply_effect(
    mode: InterruptionType, effect: EffectDeclaration | None
) -> InterruptionType:
    if effect is None:
        return mode
    if (
        effect.interruption_start is not None
        and effect.interruption_start != InterruptionType.NONE
    ):
        return effect.interruption_start
    if effect.interruption_stop in {InterruptionType.ANY, mode}:
        return InterruptionType.NONE
    return mode


def _interruption_modes(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> Iterator[tuple[TraceAct, InterruptionType]]:
    mode = InterruptionType.NONE
    for act in trace:
        yield act, mode
        mode = _action_mode(ast, act, mode)
        if act.used_transition is not None:
            mode = _apply_effect(mode, act.used_transition.effects)


def _action_mode(
    ast: ASTNodeManager, act: TraceAct, mode: InterruptionType
) -> InterruptionType:
    effect = act.action.effects or act.action.rule.effects
    if effect is not None:
        return _apply_effect(mode, effect)
    if act.action.rule.role in {"BEGIN", "END"} or act.action.ast_id is None:
        return mode
    node = ast.get(act.action.ast_id)
    node_modes = {
        "break_statement": InterruptionType.BREAK,
        "continue_statement": InterruptionType.CONTINUE,
        "return_statement": InterruptionType.RETURN,
    }
    return node_modes.get(node["type"], mode) if node is not None else mode


def has_interruption_exits_constructs(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """An active interruption caused a construct exit (main.tpg, steps 3.2/6)."""
    return any(
        mode != InterruptionType.NONE
        and act.action.rule.role == "END"
        and ast.exists(act.action.parent.ast_id)
        for act, mode in _interruption_modes(ast, trace)
    )


def has_condition_value_selects_next(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """A used transition depends on a condition value (5.2.2.5/creditCondition)."""
    return any(
        act.used_transition is not None
        and act.used_transition.constraints is not None
        and act.used_transition.constraints.condition_value is not None
        and ast.exists(act.action.parent.ast_id)
        for act in trace
    )


def has_construct_entered_before_inner(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """Execution crossed an explicit construct entry (5.2.1)."""
    return any(
        act.action.rule.role == "BEGIN"
        and act.action.is_opaque
        and "program" not in act.action.parent.rule.kind_classes
        and ast.exists(act.action.parent.ast_id)
        for act in trace
    )


def has_inner_construct_finished_before_next(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """A nested/unfolded construct finished before a subsequent step (5.2.3)."""
    for run in construct_runs(trace):
        if run.end is None or not ast.exists(run.construct.ast_id):
            continue
        if (
            run.parent is None
            and run.construct.parent is None
            and run.acts[0].unfolded_from is None
        ):
            continue
        if run.parent is not None:
            end = run.parent.end + 1 if run.parent.end is not None else len(trace)
            if any(act.action.is_opaque for act in trace[run.end + 1 : end]):
                return True
            continue
        if any(
            act.action.is_opaque and not is_within(act.action.parent, run.construct)
            for act in trace[run.end + 1 :]
        ):
            return True
    return False


def has_passed_action_repeat(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """A performed step is subject to repeat restrictions, even outside loops.

    main.tpg rejects reselecting a completed action and credits valid repeats;
    participation does not require an actual duplicate or an incorrect answer.
    """
    return any(
        act.action.rule.role not in {"BEGIN", "END"}
        and act.action.is_opaque
        and act.action.ast_id is not None
        and ast.exists(act.action.ast_id)
        for act in trace
    )


def has_containing_action_before_inner(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """An explicit containing action precedes its postorder unfolding (5.2.2.1)."""
    for run in construct_runs(trace):
        if run.construct.rule.preorder or not run.acts[0].action.is_opaque:
            continue
        if not ast.exists(run.construct.ast_id):
            continue
        initiating = run.acts[0].unfolded_from
        if initiating is None:
            initiating = next(
                (
                    act.action
                    for act in reversed(trace[: run.begin])
                    if act.action.ast_id == run.construct.ast_id
                    and act.action.parent is not run.construct
                    and act.action.rule.role not in {"BEGIN", "END"}
                ),
                None,
            )
        if initiating is None or not initiating.is_opaque:
            continue
        if not any(act.action is initiating for act in trace[: run.begin]):
            continue
        end = run.end if run.end is not None else len(trace)
        if any(act.action.is_opaque for act in trace[run.begin + 1 : end]):
            return True
    return False


def has_alternative_single_branch(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """A branch of an alternative was selected (5.2.2.2)."""
    return any(
        "alternative" in act.action.parent.rule.kind_classes
        and (
            act.action.rule.generalization == "branch"
            or act.action.rule.role in {"if_branch", "else_branch"}
        )
        and ast.exists(act.action.parent.ast_id)
        for act in trace
    )


def has_alternative_conditions_in_order(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """At least two distinct conditions were checked in one activation (5.2.2.3)."""
    return any(
        "alternative" in run.construct.rule.kind_classes
        and ast.exists(run.construct.ast_id)
        and len(
            {
                act.action.ast_id
                for act in run.acts
                if "condition" in act.action.rule.kind_classes
            }
        )
        > 1
        for run in construct_runs(trace)
    )


def has_actions_in_order(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """Distinct explicit actions occurred at the same level (5.2.2.2-3)."""
    return any(
        ast.exists(run.construct.ast_id)
        and len(
            {
                id(act.action)
                for act in run.acts
                if act.action.is_opaque and act.action.rule.role not in {"BEGIN", "END"}
            }
        )
        > 1
        for run in construct_runs(trace)
    )


def has_no_early_exit_without_interruption(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """An executed role offers an END transition requiring interruption (5.2.2.4)."""
    for act, mode in _interruption_modes(ast, trace):
        if _action_mode(ast, act, mode) != InterruptionType.NONE or not ast.exists(
            act.action.parent.ast_id
        ):
            continue
        if act.action.rule.role in {"BEGIN", "END"}:
            continue
        for transition in act.action.possible_transitions():
            if transition.to_role != "END" or transition.constraints is None:
                continue
            if transition.constraints.interruption_mode in {
                InterruptionType.BREAK,
                InterruptionType.CONTINUE,
                InterruptionType.RETURN,
                InterruptionType.EXCEPTION,
            }:
                return True
    return False


def has_function_body_runs_on_call(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """A function body was entered, rather than merely declared (step 3.1)."""
    return any(
        act.action.rule.role == "BEGIN"
        and is_function_construct(ast, act.action.parent)
        for act in trace
    )


def has_function_not_resumed_after_exit(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> bool:
    """A function activation finished (step 3.1); a later call may enter it again."""
    return any(
        run.end is not None and is_function_construct(ast, run.construct)
        for run in construct_runs(trace)
    )


def is_everything_evaluated(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> bool:
    """Program-completion marker (step 2a), deliberately excluded from skills."""
    return bool(trace) and (
        trace[-1].action.rule.role == "END"
        and trace[-1].action.parent.rule.name == "global_statements_structure"
        and ast.exists(trace[-1].action.parent.ast_id)
    )


SKILL_PREDICATES: dict[str, TracePredicate] = {
    "interruption_exits_constructs": has_interruption_exits_constructs,
    "condition_value_selects_next": has_condition_value_selects_next,
    "construct_entered_before_inner": has_construct_entered_before_inner,
    "inner_construct_finished_before_next": has_inner_construct_finished_before_next,
    "passed_action_repeat": has_passed_action_repeat,
    "containing_action_before_inner": has_containing_action_before_inner,
    "alternative_single_branch": has_alternative_single_branch,
    "alternative_conditions_in_order": has_alternative_conditions_in_order,
    "actions_in_order": has_actions_in_order,
    "no_early_exit_without_interruption": has_no_early_exit_without_interruption,
    "function_body_runs_on_call": has_function_body_runs_on_call,
    "function_not_resumed_after_exit": has_function_not_resumed_after_exit,
}


def collect_skills(ast: ASTNodeManager, trace: Sequence[TraceAct]) -> set[str]:
    """Collect participating skills, not the verdicts of a student-answer check."""
    return {
        name for name, predicate in SKILL_PREDICATES.items() if predicate(ast, trace)
    }
