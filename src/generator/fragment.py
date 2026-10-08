"""Проверка фрагмента перед генерацией задач и его метаданные."""

from __future__ import annotations

from src.ast_managers import CodeManager
from src.generator.helpers.call_graph import (
    call_graph,
    enclosing_function,
    function_name,
    recursive_functions,
)
from src.generator.registry import SituationRegistry
from src.generator.value_plan import exact_loop_iterations, is_loop

# Точки решения для цикломатической сложности, кроме циклов (их ищет иерархия типов).
_DECISION_TYPES = frozenset({"condition_branch", "ternary_operator"})


def fragment_rejections(
    registry: SituationRegistry, *, max_loop_iterations: int
) -> list[str]:
    """Причины, по которым фрагмент не годится для генерации задач."""
    code = registry.code
    reasons: list[str] = []
    for loop in code.ast.find_paths_by_type("loop", include_subtypes=True):
        node = code.ast.get(loop.id) or {}
        estimate = node.get("iteration_estimate")
        kind = estimate.get("kind") if isinstance(estimate, dict) else None
        if loop.type == "infinite_loop" or kind == "infinite":
            reasons.append(f"{_at(code, loop.id)}бесконечный цикл")

    recursive = recursive_functions(call_graph(registry))
    for action in registry.all_actions():
        if not action.is_condition:
            continue
        construct = action.parent
        if action.assumed_value is not None and action.ast_id == 0:
            reasons.append(f"{_at(code, construct.ast_id)}цикл без условия")
            continue
        if action.annotation is not None:
            continue
        if is_loop(construct):
            iterations = exact_loop_iterations(construct)
            if iterations is not None and iterations > max_loop_iterations:
                reasons.append(
                    f"{_at(code, construct.ast_id)}цикл выполняется {iterations} раз, "
                    f"допустимо не больше {max_loop_iterations}"
                )
        function = enclosing_function(registry, construct)
        if function.ast_id in recursive:
            reasons.append(
                f"{_at(code, action.ast_id)}условие в рекурсивной функции "
                f"{function_name(function)} требует <! … >"
            )
    return list(dict.fromkeys(reasons))


def cyclomatic_complexity(code: CodeManager) -> int:
    """M = 1 + число точек решения: условия ветвей, циклы, тернарные операторы, case."""
    decisions = sum(
        1
        for _, (path, _) in code.ast
        if path.type in _DECISION_TYPES
        or path.instanceof("loop")
        or (path.instanceof("case_block") and path.type != "default_case_block")
    )
    return 1 + decisions


def first_code_line(code: CodeManager) -> str:
    return next((line.strip() for line in code.code.splitlines() if line.strip()), "")


def _at(code: CodeManager, ast_id: int | None) -> str:
    line = code.code_line_number_by_id(ast_id) if ast_id is not None else None
    return f"строка {line}: " if line is not None else ""
