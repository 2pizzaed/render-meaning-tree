import textwrap

import pytest

from src.generator.helpers.call_graph import (
    call_graph,
    function_name,
    recursive_functions,
)
from src.generator.registry import SituationRegistry
from src.generator.utilities import code_snippet_to_registry
from src.generator.value_plan import ValuePlan, plan_values

pytestmark = pytest.mark.filterwarnings("ignore:No construct declaration found")


def _registry(code: str, language: str = "python") -> SituationRegistry:
    return code_snippet_to_registry(textwrap.dedent(code), language=language)


def _plan(registry: SituationRegistry, *, random_variants: int = 0, seed: int = 1806) -> ValuePlan:
    return plan_values(
        registry,
        max_loop_iterations=4,
        random_variants=random_variants,
        max_variants=48,
        seed=seed,
    )


def _patterns(plan: ValuePlan) -> list[list[tuple[bool, ...]]]:
    return [list(variant.patterns.values()) for variant in plan.variants]


def test_loop_with_nested_branch_is_covered_by_iteration_count_variants():
    registry = _registry(
        """
        while x > 0:
            if y:
                x = 1
            else:
                x = 2
        """
    )

    plan = _plan(registry)

    assert [point.domain for point in plan.points] == [(0, 1, 2, 3, 4), (0, 1)]
    outcomes = [list(variant.outcomes.values()) for variant in plan.variants]
    assert [values[0] for values in outcomes] == [0, 1, 2, 3, 4]
    # При нуле итераций ветвление недостижимо и его выбор стёрт.
    assert outcomes[0] == [0]
    assert outcomes[1] == [1, 0]
    assert outcomes[2] == [2, 1]
    assert plan.variants[1].description.startswith("while@")


def test_sequential_branches_need_two_coverage_variants():
    registry = _registry(
        """
        if a:
            x = 1
        if b:
            x = 2
        if c:
            x = 3
        """
    )

    plan = _plan(registry)

    assert [variant.outcomes and set(variant.outcomes.values()) for variant in plan.variants] == [
        {0},
        {1},
    ]
    assert _patterns(plan) == [[(True,)] * 3, [(False,)] * 3]


def test_random_variants_are_deduplicated_and_reproducible():
    code = """
        if a:
            x = 1
        if b:
            x = 2
        """
    first = _plan(_registry(code), random_variants=16)
    second = _plan(_registry(code), random_variants=16)

    descriptions = [variant.description for variant in first.variants]
    assert len(descriptions) == len(set(descriptions)) == 4
    assert descriptions == [variant.description for variant in second.variants]


def test_branch_patterns_mark_previous_conditions_false():
    registry = _registry(
        """
        if a:
            x = 1
        elif b:
            x = 2
        else:
            x = 3
        """
    )

    plan = _plan(registry)

    [point] = plan.points
    assert point.domain == (0, 1, 2)
    assert [point.patterns(outcome) for outcome in point.domain] == [
        dict(zip(point.conditions, [(True,), (True,)], strict=True)),
        dict(zip(point.conditions, [(False,), (True,)], strict=True)),
        dict(zip(point.conditions, [(False,), (False,)], strict=True)),
    ]
    assert [variant.description.split("=")[1] for variant in plan.variants] == [
        "if",
        "elif1",
        "else",
    ]


def test_constant_condition_and_exact_loop_are_fixed_points():
    registry = _registry(
        """
        if True:
            x = 1
        else:
            x = 2
        for i in range(3):
            x += i
        """
    )

    plan = _plan(registry)

    assert [point.domain for point in plan.points] == [(0,), (3,)]
    [variant] = plan.variants
    assert variant.description == "без точек выбора"
    assert sorted(variant.patterns.values()) == [(True,), (True, True, True, False)]


def test_do_while_domain_starts_from_one_iteration():
    registry = _registry(
        """
        int main() {
            int x = 0;
            do {
                x++;
            } while (x < y);
            return 0;
        }
        """,
        "c++",
    )

    plan = _plan(registry)

    [point] = plan.points
    assert point.kind == "do_while"
    assert point.domain == (1, 2, 3, 4)
    assert point.patterns(1) == {point.conditions[0]: (False,)}
    assert point.patterns(3) == {point.conditions[0]: (True, True, False)}


def test_annotated_condition_is_not_a_choice_point():
    registry = _registry(
        """
        while x > 0:  # <! TF >
            x -= 1
        if y:
            x = 1
        """
    )

    plan = _plan(registry)

    assert [point.label.split("@")[0] for point in plan.points] == ["if"]
    assert all(len(variant.patterns) == 1 for variant in plan.variants)


def test_function_points_are_reachable_only_through_reachable_calls():
    registry = _registry(
        """
        def f(x):
            while x > 0:
                x -= 1
        if y:
            f(3)
        """
    )

    plan = _plan(registry)

    [loop, branch] = plan.points
    for variant in plan.variants:
        called = variant.outcomes.get(branch.construct_ast_id) == 0
        assert (loop.construct_ast_id in variant.outcomes) == called
    assert {variant.outcomes.get(loop.construct_ast_id) for variant in plan.variants} >= {
        0,
        1,
        2,
        3,
        4,
    }


def test_call_graph_finds_direct_and_mutual_recursion():
    registry = _registry(
        """
        def even(n):
            if n == 0:
                return True
            return odd(n - 1)
        def odd(n):
            if n == 0:
                return False
            return even(n - 1)
        def fact(n):
            if n <= 1:
                return 1
            return n * fact(n - 1)
        def helper(n):
            return n
        even(2)
        fact(3)
        helper(1)
        """
    )

    sites = call_graph(registry)
    recursive = recursive_functions(sites)

    names = {site.callee.ast_id: function_name(site.callee) for site in sites}
    assert {names[ast_id] for ast_id in recursive} == {"even", "odd", "fact"}
    assert len(sites) == 6
