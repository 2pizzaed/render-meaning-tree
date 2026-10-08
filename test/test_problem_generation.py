import logging
import textwrap
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from src.ast_managers import prepare_code
from src.generator.pipeline import LearningProblemGeneratorPipeline
from src.generator.problems import (
    DEFAULT_MODEL_DIR,
    DEFAULT_SEED,
    LearningProblem,
    ProblemGenerationConfig,
)
from src.generator.utilities import code_snippet_to_problems, code_snippet_to_registry
from src.helpers.tpg.reasoning import solve_graph_full_reasoning
from src.model.situation import SemanticValue

RECURSIVE_FACT = """
    def fact(n):
        if n <= 1:{marker}
            return 1
        return n * fact(n - 1)
    fact(3)
    """


def _checked(code: str, language: str = "python") -> LearningProblemGeneratorPipeline:
    manager = prepare_code(textwrap.dedent(code), language)  # type: ignore[arg-type]
    return LearningProblemGeneratorPipeline.from_code(manager).run_until("check_fragment")


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        pytest.param(
            "while True:\n    x = 1\n    break\n", "строка 1: бесконечный цикл", id="infinite"
        ),
        pytest.param(
            "for i in range(10):\n    print(i)\n",
            "строка 1: цикл выполняется 10 раз, допустимо не больше 4",
            id="too-many-iterations",
        ),
        pytest.param(
            RECURSIVE_FACT.format(marker=""),
            "условие в рекурсивной функции fact требует <! … >",
            id="recursion",
        ),
    ],
)
def test_check_fragment_rejects_fragment_with_reason(code: str, reason: str):
    pipeline = _checked(code)

    assert pipeline.is_terminated
    assert pipeline.termination_reason is not None
    assert reason in pipeline.termination_reason


def test_check_fragment_accepts_annotated_recursion_and_exact_short_loop():
    pipeline = _checked(
        RECURSIVE_FACT.format(marker="  # <! FFT >")
        + "for i in range(3):\n    print(i)\n"
    )

    assert not pipeline.is_terminated
    assert pipeline.registry.fragment is not None


def test_check_fragment_counts_cyclomatic_complexity():
    pipeline = _checked(
        """
        x = 3
        while x > 0:
            if x == 1:
                x = 0
            elif x == 2:
                x = 5 if x else 6
            x -= 1
        """
    )

    assert pipeline.registry.fragment is not None
    # while, if, elif, тернарный оператор.
    assert pipeline.registry.fragment.cyclomatic_complexity == 5


# --- Интеграционные тесты: findCorrect через RPC ---

FAST_CONFIG = ProblemGenerationConfig(random_variants=0, max_loop_iterations=2)

# Ошибки графа findCorrect при повторном выполнении конструкта в том же кадре
# (итерации цикла): диагностика - docs/ideas/findcorrect_reentry_issues.md.
REPEATED_CALL_XFAIL = pytest.mark.xfail(
    reason="findCorrect: раскрутка return пропускает конструкт вызова, "
    "уже завершённый в этом кадре на прошлой итерации",
    strict=True,
)
BRANCH_REENTRY_XFAIL = pytest.mark.xfail(
    reason="findCorrect: при повторном входе в ветвление checkRepeatedAction "
    "пропускает условия и выбирает ещё не выполнявшуюся ветвь",
    strict=True,
)

FACT6_FRAGMENTS = [
    pytest.param(
        """
        def g(x):
            while x > 0:
                x -= 1
            return x
        y = 1
        while g(y) > -1 and y < 3:
            y += 1
        """,
        id="call-in-loop-condition",
        marks=REPEATED_CALL_XFAIL,
    ),
    pytest.param(
        """
        def g(x):
            while x > 0:
                x -= 1
            return x
        y = 0
        if g(y) > -1:
            y += 1
        """,
        id="call-in-if-condition",
    ),
    pytest.param(
        """
        i = 0
        while i < 2:
            j = 0
            while j < 2:
                j += 1
            i += 1
        """,
        id="nested-loops",
    ),
    pytest.param(
        """
        x = 0
        while x < 5:
            x += 1
            if x > 1:
                break
        """,
        id="break",
    ),
]


def _problems(
    code: str, config: ProblemGenerationConfig = FAST_CONFIG, seed: int = DEFAULT_SEED
) -> list[LearningProblem]:
    return code_snippet_to_problems(textwrap.dedent(code), seed=seed, config=config)


def _reasons(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == "src.pipeline"]


@pytest.mark.parametrize("code", FACT6_FRAGMENTS)
def test_condition_is_evaluated_at_most_once_per_reasoner_call(code: str, tmp_path: Path):
    registry = code_snippet_to_registry(textwrap.dedent(code))
    for action in registry.all_actions():
        if action.is_condition:
            pattern = (True, False) if "loop" in action.parent.rule.kind_classes else (True,)
            action.values = [SemanticValue(value) for value in pattern * 10]
            action.bind_values()
    registry.variables["P"] = registry.trace_acts[-1]
    stops: set[int] = set()

    solve_graph_full_reasoning(
        tmp_path, registry, model_dir=DEFAULT_MODEL_DIR, max_iterations=60, solver_stops=stops
    )

    start = 0
    for stop in sorted(stops):
        window = registry.trace_acts[start : stop + 1]
        evaluations = Counter(id(act.action) for act in window if act.action.is_condition)
        assert max(evaluations.values(), default=0) <= 1
        start = stop + 1


@pytest.mark.parametrize("code", FACT6_FRAGMENTS)
def test_generated_chains_are_reloaded_without_reasoner_failures(
    code: str, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.INFO):
        problems = _problems(code)

    assert problems
    assert not [reason for reason in _reasons(caplog) if "findCorrect" in reason]


def test_repeated_calls_reload_loop_chain_per_entry():
    problems = _problems(
        """
        def f(x):
            while x > 0:
                x -= 1
        f(5)
        f(3)
        """
    )

    assert {problem.variant.split("=")[1] for problem in problems} == {"0", "1", "2"}
    two_iterations = next(problem for problem in problems if problem.variant.endswith("=2"))
    assert list(two_iterations.values.values()) == [(True, True, False) * 2]


def test_loop_with_nested_branch_gives_different_problems():
    problems = _problems(
        """
        x = 3
        while x > 0:
            if x % 2 == 0:
                x -= 2
            else:
                x -= 1
        """
    )

    assert len(problems) >= 3
    assert len({tuple(problem.values.items()) for problem in problems}) == len(problems)
    assert all(problem.score is not None for problem in problems)


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("while True:\n    x = 1\n    break\n", "бесконечный цикл"),
        ("for i in range(10):\n    print(i)\n", "цикл выполняется 10 раз"),
        (RECURSIVE_FACT.format(marker=""), "требует <! … >"),
    ],
    ids=["infinite", "too-many-iterations", "recursion"],
)
def test_rejected_fragment_gives_no_problems_with_logged_reason(
    code: str, reason: str, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.INFO):
        problems = _problems(code)

    assert problems == []
    assert any(reason in message for message in _reasons(caplog))


def test_annotated_recursion_gives_problem():
    [problem] = _problems(RECURSIVE_FACT.format(marker="  # <! FFT >"))

    assert list(problem.values.values()) == [(False, False, True)]
    assert "recursion" in problem.concepts


def test_exhausted_manual_chain_terminates_branch_with_line(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO):
        problems = _problems(
            """
            def f(x):
                while x > 0:  # <! TF >
                    x -= 1
            f(1)
            f(1)
            """
        )

    assert problems == []
    assert any(
        "строка 2: цепочка <! TF > кончилась на 3-м вычислении условия" in message
        for message in _reasons(caplog)
    )


def test_same_seed_gives_same_problems():
    code = """
        x = 3
        while x > 0:
            if x == 2:
                x -= 2
            x -= 1
        """
    config = replace(FAST_CONFIG, random_variants=4, top_k=3, selection="random")

    def summary(seed: int) -> list[tuple[object, ...]]:
        return [
            (problem.variant, problem.values, problem.steps, problem.skills, problem.score)
            for problem in _problems(code, config, seed)
        ]

    assert summary(7) == summary(7)


def test_exhausted_budget_terminates_remaining_branches(caplog: pytest.LogCaptureFixture):
    code = """
        def f(x):
            while x > 0:
                x -= 1
        f(3)
        """
    with caplog.at_level(logging.INFO):
        problems = _problems(code, replace(FAST_CONFIG, reasoner_call_budget=1))

    assert problems == []
    exhausted = [
        message
        for message in _reasons(caplog)
        if "бюджет вызовов рассуждателя исчерпан (1)" in message
    ]
    # По ветке на число итераций цикла: 0, 1, 2.
    assert len(exhausted) == FAST_CONFIG.max_loop_iterations + 1


@BRANCH_REENTRY_XFAIL
def test_branch_condition_is_evaluated_on_every_loop_iteration():
    problems = _problems(
        """
        xs = [1, 2]
        for ch in xs:
            if ch == 10:
                y = 1
        """
    )

    assert problems
    for problem in problems:
        chains = {role: values for (_, role), values in problem.values.items()}
        # Невычисленному условию trim_values оставляет одно значение.
        iterations = max(chains["cond"].count(True), 1)
        assert len(chains["first_cond"]) == iterations, problem.variant
