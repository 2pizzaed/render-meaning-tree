import logging
import textwrap

import pytest

from src.generator.problems import ProblemGenerationConfig
from src.generator.utilities import code_snippet_to_problems
from test.tools.annotate_trace import AnnotateTraceError, annotate


def _annotate(code: str, **kwargs: float) -> str:
    return annotate(textwrap.dedent(code).strip("\n"), **kwargs)  # type: ignore[arg-type]


def test_marks_conditions_and_calls_by_real_trace():
    annotated = _annotate(
        """
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)
        def unused(x):
            if x:
                return 1
            return 0
        class A:
            def m(self, x):
                return x
        if fib(2) > A().m(0):
            print("pos")
        for i in range(2):
            match i:
                case 0:
                    pass
                case x:
                    print(x)
        x = 3
        while x > 0:
            x -= 1
            if x == 1:
                break
        for v in [1, 2]:
            pass
        else:
            print(v)
        """
    )

    # Цель вызова - только при нескольких вызовах на строке; у метода нет self; условие
    # unused ни разу не вычислялось; у for после break нет F, у for-else F есть.
    assert annotated == textwrap.dedent(
        """\
        def fib(n):
            if n < 2:  # <! FTT >
                return n
            return fib(n - 1) + fib(n - 2)  # <! fib#1: (-, "fib(1)") > <! fib#2: (-, "fib(0)") >
        def unused(x):
            if x:
                return 1
            return 0
        class A:
            def m(self, x):
                return x
        if fib(2) > A().m(0):  # <! T > <! fib: (-, "fib(2)") > <! m: (-, "m(0)") >
            print("pos")
        for i in range(2):  # <! TTF >
            match i:
                case 0:  # <! TF >
                    pass
                case x:  # <! T >
                    print(x)
        x = 3
        while x > 0:  # <! TT >
            x -= 1
            if x == 1:  # <! FT >
                break
        for v in [1, 2]:  # <! TTF >
            pass
        else:
            print(v)"""
    )


def test_match_without_default_gets_false_for_every_checked_case():
    annotated = _annotate(
        """
        for i in range(2):
            match i:
                case 1:
                    pass
                case 2:
                    pass
        """
    )

    assert "case 1:  # <! FT >" in annotated
    assert "case 2:  # <! F >" in annotated


def test_warns_about_call_that_does_not_reach_marker_line(
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.WARNING):
        annotated = _annotate(
            """
            def f(x):
                return x
            y = [f(1),
                 2]
            """
        )

    assert "<!" not in annotated
    assert any(
        "вызов f(1) не занимает строку 4" in message for message in caplog.messages
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
            def fib(n):
                if n < 2:
                    return n
                return fib(n - 1) + fib(n - 2)
            print(fib(2))
            """,
            id="recursion",
        ),
        pytest.param(
            # Два выхода подряд из одного вызова на строке down(n - 1).
            """
            def down(n):
                if n == 0:
                    return
                print("n =", n)
                down(n - 1)
            down(2)
            """,
            id="tail-call",
        ),
        pytest.param(
            """
            def f(x):
                return x + 1
            y = f(f(1))
            print(y)
            """,
            id="nested-call",
        ),
        pytest.param(
            """
            def f(x):
                while x > 0:
                    x -= 1
            f(1)
            f(1)
            """,
            id="repeated-call",
        ),
        pytest.param(
            """
            def g(x):
                return x
            if g(1) > 0:
                print("pos")
            """,
            id="call-in-condition",
        ),
        pytest.param(
            """
            for i in range(2):
                match i:
                    case 0:
                        print("zero")
                    case _:
                        print("other")
            """,
            id="match",
        ),
    ],
)
def test_generator_consumes_traced_chains_exactly(
    code: str, caplog: pytest.LogCaptureFixture
):
    annotated = _annotate(code)

    with caplog.at_level(logging.INFO):
        problems = code_snippet_to_problems(
            annotated, config=ProblemGenerationConfig(random_variants=0)
        )

    assert problems
    assert not [
        message
        for message in caplog.messages
        if "использовано" in message or "кончилась" in message
    ]


@pytest.mark.parametrize(
    ("code", "message"),
    [
        pytest.param(
            "x = 1  # <! T >\n", r"строка 1: в сниппете уже есть разметка", id="marker"
        ),
        pytest.param(
            "x = 1; y = 2\n",
            r"строка 1: оператор должен начинать строку, а перед ним «x = 1;»",
            id="semicolon",
        ),
        pytest.param(
            "x = 1\nif x: y = 2\n",
            r"строка 2: оператор должен начинать строку, а перед ним «if x:»",
            id="one-line-if",
        ),
        pytest.param(
            "x = 1\nif x:\n    pass\nelse: y = 2\n",
            r"строка 4: .* перед ним «else:»",
            id="one-line-else",
        ),
        pytest.param(
            "match 1:\n    case 1 if True:\n        pass\n",
            r"строка 2: охрана case \(True\) не поддерживается",
            id="case-guard",
        ),
        pytest.param(
            "x = 1\nwhile x:  # step\n    x = 0\n",
            r"строка 2: метке <! TF > мешает комментарий # step",
            id="comment-on-marker-line",
        ),
        pytest.param(
            "x = input()\n", r"строка 1: сниппет ждёт ввода, а ввода нет", id="input"
        ),
        pytest.param(
            "x = 1 / 0\n",
            r"строка 1: ZeroDivisionError: division by zero",
            id="exception",
        ),
        pytest.param(
            "for i in range(1000):\n    pass\n",
            r"условие в строке 1 вычислено больше 100 раз",
            id="long-condition-chain",
        ),
        pytest.param(
            "def f(n):\n    return f(n - 1) if n else 0\nf(150)\n",
            r"вызов f в строке 2 выполнен больше 100 раз",
            id="long-call-chain",
        ),
        pytest.param(
            "import time\ntime.sleep(10)\n", r"не завершился за 1 с", id="timeout"
        ),
        pytest.param("if x\n", r"сниппет не разбирается", id="syntax"),
    ],
)
def test_rejects_snippet_that_cannot_be_annotated(code: str, message: str):
    with pytest.raises(AnnotateTraceError, match=message):
        annotate(code, timeout=1)
