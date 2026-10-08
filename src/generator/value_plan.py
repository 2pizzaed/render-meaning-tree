"""Значения условий: умолчания и план вариантов для генерации задач.

План строится без рассуждателя. Точка выбора - управляющая конструкция без разметки:
цикл (исход - число итераций одного захода) или ветвление (исход - номер выбранной
ветви, ``m`` - ни одна). Варианты сначала покрывают все пары «точка, исход», затем
добавляются случайные. Выборы для недостижимых точек стираются, поэтому варианты,
различающиеся только недостижимым кодом, совпадают.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from src.generator.helpers.call_graph import CallSite, call_graph, recursive_functions
from src.generator.helpers.trace_features import is_function_construct
from src.generator.registry import SituationRegistry
from src.model.situation import Action, Construct

logger = logging.getLogger(__name__)

DEFAULT_LOOP_VALUES = (True, True, False)
DEFAULT_BRANCH_VALUES = (True,)

# Действие-условие ищется по (ast_id, role): ветка получает вариант после clone(),
# поэтому ссылки на объекты Action указывали бы на действия родителя.
type ActionKey = tuple[int | None, str]
# Допустимые исходы точек (индекс точки -> исходы); пустой словарь - без условий.
type Requirement = dict[int, frozenset[int]]
# Дизъюнкция требований: [] - код недостижим, [{}] - достижим всегда.
type Reachability = list[Requirement]
type PointKind = Literal["loop", "do_while", "branch"]


@dataclass(frozen=True, slots=True)
class ChoicePoint:
    construct_ast_id: int
    kind: PointKind
    # Условия конструкции; у ветвления - по порядку ветвей.
    conditions: tuple[ActionKey, ...]
    domain: tuple[int, ...]
    label: str

    @property
    def is_fixed(self) -> bool:
        return len(self.domain) == 1

    def patterns(self, outcome: int) -> dict[ActionKey, tuple[bool, ...]]:
        """Шаблон одного захода в конструкцию для каждого её условия."""
        if self.kind == "branch":
            # Условия до выбранной ветви ложны, её условие истинно; дальше условия
            # не вычисляются, им достаётся любое значение.
            return {
                condition: (index >= outcome,)
                for index, condition in enumerate(self.conditions)
            }
        iterations = outcome - 1 if self.kind == "do_while" else outcome
        return {self.conditions[0]: (True,) * iterations + (False,)}

    def describe(self, outcome: int) -> str:
        if self.kind != "branch":
            return f"{self.label}={outcome}"
        if outcome == len(self.conditions):
            return f"{self.label}=else"
        return f"{self.label}={'if' if outcome == 0 else f'elif{outcome}'}"


@dataclass(frozen=True, slots=True)
class ValueVariant:
    index: int
    # Исходы достижимых нефиксированных точек: AST id конструкта -> исход.
    outcomes: dict[int, int]
    # Шаблон одного захода для каждого неразмеченного условия.
    patterns: dict[ActionKey, tuple[bool, ...]]
    description: str


@dataclass(frozen=True, slots=True)
class ValuePlan:
    points: tuple[ChoicePoint, ...]
    variants: tuple[ValueVariant, ...]


def action_key(action: Action) -> ActionKey:
    return (action.ast_id, action.rule.role)


def default_condition_values(action: Action) -> tuple[bool, ...]:
    """Цепочка без рассуждателя: разметка, затем assumed_value, затем умолчания."""
    if action.annotation is not None:
        return action.annotation.values
    if action.assumed_value is not None:
        return (action.assumed_value,)
    if not action.is_condition:
        return ()
    if is_loop(action.parent):
        return DEFAULT_LOOP_VALUES
    return DEFAULT_BRANCH_VALUES


def is_loop(construct: Construct) -> bool:
    return "loop" in construct.rule.kind_classes


def exact_loop_iterations(construct: Construct) -> int | None:
    """Точное число итераций цикла по надёжной оценке MT."""
    estimate = construct.ast_node.get("iteration_estimate")
    if not isinstance(estimate, dict) or not estimate.get("reliable"):
        return None
    iterations = estimate.get("exact_iterations")
    return iterations if isinstance(iterations, int) else None


def plan_values(
    registry: SituationRegistry,
    *,
    max_loop_iterations: int,
    random_variants: int,
    max_variants: int,
    seed: int,
) -> ValuePlan:
    points = choice_points(registry, max_loop_iterations=max_loop_iterations)
    reachability = _point_reachability(registry, points)
    rng = random.Random(f"{seed}:plan")

    coverage = _coverage_assignments(points, reachability, rng)
    if len(coverage) > max_variants:
        logger.info(
            "покрытие исходов требует %d вариантов, оставлено %d",
            len(coverage),
            max_variants,
        )
    randoms = [_random_assignment(points, rng) for _ in range(random_variants)]

    variants: list[ValueVariant] = []
    seen: set[tuple[tuple[int, int], ...]] = set()
    for assignment in (*coverage, *randoms):
        outcomes = _normalize(points, reachability, assignment)
        key = tuple(sorted(outcomes.items()))
        if key in seen:
            continue
        seen.add(key)
        variants.append(_variant(registry, points, outcomes, len(variants)))
        if len(variants) == max_variants:
            break
    return ValuePlan(points=tuple(points), variants=tuple(variants))


def choice_points(
    registry: SituationRegistry, *, max_loop_iterations: int
) -> list[ChoicePoint]:
    """Точки выбора в порядке исходного кода; размеченные конструкции не входят."""
    code = registry.code
    points: list[tuple[int, ChoicePoint]] = []
    for construct in registry.constructs.values():
        conditions = [action for action in construct.actions if action.is_condition]
        if not conditions or any(action.annotation is not None for action in conditions):
            continue
        node_type = str(construct.ast_node.get("type", ""))
        line = code.code_line_number_by_id(construct.ast_id)
        place = line if line is not None else f"#{construct.ast_id}"
        label = f"{node_type.removesuffix('_loop').removesuffix('_statement')}@{place}"
        keys = tuple(action_key(action) for action in conditions)
        kind: PointKind
        if not is_loop(construct):
            kind = "branch"
            domain = _branch_domain(conditions)
        else:
            kind = "do_while" if node_type == "do_while_loop" else "loop"
            domain = _loop_domain(construct, kind, max_loop_iterations)
        token_range = code.token_index_range(construct.ast_id)
        order = token_range[0] if token_range is not None else construct.ast_id
        points.append((order, ChoicePoint(construct.ast_id, kind, keys, domain, label)))
    return [point for _, point in sorted(points, key=lambda item: item[0])]


def _loop_domain(
    construct: Construct, kind: str, max_loop_iterations: int
) -> tuple[int, ...]:
    exact = exact_loop_iterations(construct)
    if exact is not None:
        # Больше max_loop_iterations отклоняет check_fragment.
        return (exact,)
    first = 1 if kind == "do_while" else 0
    return tuple(range(first, max_loop_iterations + 1))


def _branch_domain(conditions: list[Action]) -> tuple[int, ...]:
    """Исход j: условия до j ложны, условие j истинно; j = m - все ложны."""
    domain = list(range(len(conditions) + 1))
    for index, action in enumerate(conditions):
        value = _constant_value(action)
        if value is True:
            # Условие всегда истинно: следующие ветви недостижимы.
            domain = [outcome for outcome in domain if outcome <= index]
        elif value is False:
            domain = [outcome for outcome in domain if outcome != index]
    return tuple(domain)


def _constant_value(action: Action) -> bool | None:
    node = action.ast_node
    if node is None:
        return None
    estimate = node.get("value_estimate")
    value = estimate.get("exact_value") if isinstance(estimate, dict) else None
    if isinstance(value, bool):
        return value
    if node.get("type") == "bool_literal":
        literal = node.get("value")
        return literal if isinstance(literal, bool) else None
    return None


def _point_reachability(
    registry: SituationRegistry, points: list[ChoicePoint]
) -> list[Reachability]:
    reachability = _ReachabilityAnalysis(registry, points)
    return [
        reachability.of(registry.constructs[point.construct_ast_id]) for point in points
    ]


class _ReachabilityAnalysis:
    """При каких исходах точек выполняется конструкт (хотя бы начинается)."""

    def __init__(self, registry: SituationRegistry, points: list[ChoicePoint]) -> None:
        self.registry = registry
        self.points = points
        self.point_index = {point.construct_ast_id: index for index, point in enumerate(points)}
        sites = call_graph(registry)
        self.recursive = recursive_functions(sites)
        self.sites_by_callee: dict[int, list[CallSite]] = {}
        for site in sites:
            self.sites_by_callee.setdefault(site.callee.ast_id, []).append(site)
        self.cache: dict[int, Reachability] = {}

    def of(self, construct: Construct) -> Reachability:
        cached = self.cache.get(id(construct))
        if cached is None:
            cached = self._compute(construct)
            self.cache[id(construct)] = cached
        return cached

    def _compute(self, construct: Construct) -> Reachability:
        if is_function_construct(self.registry.code.ast, construct):
            # Функция достижима, если достижимо хотя бы одно место её вызова. Вызов
            # из рекурсивной функции считается достижимым: её условия размечены.
            return _union(
                [{}]
                if site.caller.ast_id in self.recursive
                else self.of(site.call)
                for site in self.sites_by_callee.get(construct.ast_id, [])
            )
        parent = construct.parent
        if parent is None:
            return [{}]
        reachability = self.of(parent)
        index = self.point_index.get(parent.ast_id)
        if index is None:
            return reachability
        allowed = self._allowed_outcomes(self.points[index], parent, construct)
        return reachability if allowed is None else _require(reachability, index, allowed)

    def _allowed_outcomes(
        self, point: ChoicePoint, parent: Construct, child: Construct
    ) -> frozenset[int] | None:
        """Исходы точки parent, при которых выполняется child; None - при любых."""
        steps = self._path_below(parent, child)
        domain = frozenset(point.domain)
        if point.kind != "branch":
            in_body = any(field == "body" for field, _ in steps)
            return frozenset(outcome for outcome in domain if outcome >= 1) if in_body else None
        if not steps:
            return None
        field, branch = steps[0]
        if field == "elseBranch":
            return domain & {len(point.conditions)}
        if field != "branches" or not isinstance(branch, int):
            return None
        if len(steps) > 1 and steps[1][0] == "condition":
            # Условие ветви k вычисляется, когда все предыдущие ложны.
            return frozenset(outcome for outcome in domain if outcome >= branch)
        return domain & {branch}

    def _path_below(
        self, parent: Construct, child: Construct
    ) -> list[tuple[str | None, int | str | None]]:
        """Поля AST от узла parent вниз до узла child: (имя поля, индекс в контейнере)."""
        steps: list[tuple[str | None, int | str | None]] = []
        current = self.registry.code.ast.get_path(child.ast_id)
        while current is not None and current.id != parent.ast_id:
            steps.append((current.field_name, current.container_field_id))
            current = current.parent
        return list(reversed(steps))


def _require(
    reachability: Reachability, index: int, allowed: frozenset[int]
) -> Reachability:
    result: Reachability = []
    for requirement in reachability:
        narrowed = requirement.get(index, allowed) & allowed
        if narrowed:
            result.append({**requirement, index: narrowed})
    return result


def _union(parts: Iterable[Reachability]) -> Reachability:
    result: Reachability = []
    for part in parts:
        for requirement in part:
            if not requirement:
                return [{}]
            if requirement not in result:
                result.append(requirement)
    return result


def _is_satisfied(reachability: Reachability, assignment: dict[int, int]) -> bool:
    return any(
        all(assignment.get(index) in allowed for index, allowed in requirement.items())
        for requirement in reachability
    )


def _fixed_assignment(points: list[ChoicePoint]) -> dict[int, int]:
    return {index: point.domain[0] for index, point in enumerate(points) if point.is_fixed}


def _coverage_assignments(
    points: list[ChoicePoint], reachability: list[Reachability], rng: random.Random
) -> list[dict[int, int]]:
    """Жадное покрытие пар «точка, исход» в порядке исходного кода."""
    targets = [
        (index, outcome)
        for index, point in enumerate(points)
        if not point.is_fixed
        for outcome in point.domain
    ]
    uncovered = [
        target
        for target in targets
        if _assign_target(_fixed_assignment(points), target, reachability, set())
    ]
    assignments: list[dict[int, int]] = []
    while uncovered:
        assignment = _fixed_assignment(points)
        pending = set(uncovered)
        for target in uncovered:
            _assign_target(assignment, target, reachability, pending)
        for index, point in enumerate(points):
            if index not in assignment:
                assignment[index] = rng.choice(point.domain)
        covered = _normalize(points, reachability, assignment).items()
        uncovered = [target for target in uncovered if target not in covered]
        assignments.append(assignment)
    # Без достижимых целей (все точки фиксированы) вариант всё равно один.
    return assignments or [_random_assignment(points, rng)]


def _assign_target(
    assignment: dict[int, int],
    target: tuple[int, int],
    reachability: list[Reachability],
    pending: set[tuple[int, int]],
) -> bool:
    """Выставить точке исход и сделать её достижимой, не меняя уже выбранное."""
    index, outcome = target
    if assignment.get(index, outcome) != outcome:
        return False
    for requirement in reachability[index]:
        if any(
            ancestor in assignment and assignment[ancestor] not in allowed
            for ancestor, allowed in requirement.items()
        ):
            continue
        for ancestor, allowed in sorted(requirement.items()):
            if ancestor not in assignment:
                options = sorted(allowed)
                preferred = [option for option in options if (ancestor, option) in pending]
                assignment[ancestor] = (preferred or options)[0]
        assignment[index] = outcome
        pending.discard(target)
        return True
    return False


def _random_assignment(points: list[ChoicePoint], rng: random.Random) -> dict[int, int]:
    return {index: rng.choice(point.domain) for index, point in enumerate(points)}


def _normalize(
    points: list[ChoicePoint],
    reachability: list[Reachability],
    assignment: dict[int, int],
) -> dict[int, int]:
    """Исходы достижимых нефиксированных точек; остальные выборы стираются."""
    return {
        index: outcome
        for index, outcome in assignment.items()
        if not points[index].is_fixed and _is_satisfied(reachability[index], assignment)
    }


def _variant(
    registry: SituationRegistry,
    points: list[ChoicePoint],
    outcomes: dict[int, int],
    index: int,
) -> ValueVariant:
    patterns: dict[ActionKey, tuple[bool, ...]] = {}
    # Условия вне точек (в частично размеченном ветвлении) повторяют умолчание.
    for action in registry.all_actions():
        if action.is_condition and action.annotation is None:
            patterns[action_key(action)] = default_condition_values(action)
    for point_index, point in enumerate(points):
        # Недостижимой точке нужен любой корректный шаблон: она не вычисляется,
        # а если анализ ошибся, хук всё равно догрузит цепочку.
        patterns.update(point.patterns(outcomes.get(point_index, point.domain[0])))
    description = ", ".join(
        points[point_index].describe(outcome) for point_index, outcome in sorted(outcomes.items())
    )
    return ValueVariant(
        index=index,
        outcomes={points[point_index].construct_ast_id: outcome for point_index, outcome in outcomes.items()},
        patterns=patterns,
        description=description or "без точек выбора",
    )
