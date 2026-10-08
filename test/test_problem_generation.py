import textwrap

import pytest

from src.ast_managers import prepare_code
from src.generator.pipeline import LearningProblemGeneratorPipeline

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
