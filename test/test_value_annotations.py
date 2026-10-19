import textwrap

import pytest

from src.ast_managers import prepare_code
from src.coderenderer.entities import Token
from src.coderenderer.html import prepare_html_context
from src.generator.utilities import code_snippet_to_registry
from src.generator.value_annotations import strip_value_markers


def _annotations(code: str, language: str) -> dict[tuple[str, str], str]:
    registry = code_snippet_to_registry(textwrap.dedent(code), language=language)
    return {
        (action.parent.rule.name, action.rule.role): action.annotation.marker
        for action in registry.all_actions()
        if action.annotation is not None
    }


def test_python_markers_bind_to_loop_and_branch_conditions():
    annotations = _annotations(
        """
        def f(x, xs):
            while x > 0:  # <! TTF >
                x -= 1
            if x == 1:  # <!F>
                pass
            elif x == 2:  # <! T >
                pass
            for v in xs:  # <! TF >
                pass
            for i in range(3):  # <! TTTF >
                pass
        f(5, [1])
        """,
        "python",
    )

    assert annotations == {
        ("while_structure", "cond"): "<! TTF >",
        ("if_structure", "first_cond"): "<! F >",
        ("if_structure", "next_cond"): "<! T >",
        ("for_each_structure", "cond"): "<! TF >",
        ("for_range_structure", "cond"): "<! TTTF >",
    }


def test_cpp_markers_bind_to_conditions_including_do_while_and_c_like_for():
    annotations = _annotations(
        """
        int main() {
            int x = 3;
            while (x > 0) { // <! TF >
                x--;
            }
            if (x > 2) // <! T >
                x = 1;
            else if (x > 1) { // <! F >
                x = 2;
            }
            do {
                x++;
            } while (x < 3); // <! TTF >
            for (int i = 0; i < x; i++) { // <! TTTF >
                x--;
            }
            return 0;
        }
        """,
        "c++",
    )

    assert annotations == {
        ("while_structure", "cond"): "<! TF >",
        ("if_structure", "first_cond"): "<! T >",
        ("if_structure", "next_cond"): "<! F >",
        ("do_while_structure", "cond"): "<! TTF >",
        ("for_range_structure", "cond"): "<! TTTF >",
    }


def test_java_marker_binds_to_for_each_container():
    annotations = _annotations(
        """
        public class Main {
            public static void main(String[] args) {
                int[] arr = {1, 2};
                int x = 0;
                for (int v : arr) { // <! TTF >
                    x += v;
                }
            }
        }
        """,
        "java",
    )

    assert annotations == {("for_each_structure", "cond"): "<! TTF >"}


def test_annotated_condition_gets_manual_values_by_default():
    registry = code_snippet_to_registry("while x > 0:  # <! TF >\n    x -= 1\n")

    [condition] = [action for action in registry.all_actions() if action.is_condition]

    assert [value.bool_value for value in condition.values] == [True, False]


@pytest.mark.parametrize(
    ("code", "language"),
    [
        (
            (
                'def f(n):\n    if n > 0:  # <! (T, "n > 0, n=1"), (F, "f(0)") >\n'
                "        f(n - 1)\nf(1)\n"
            ),
            "python",
        ),
        (
            (
                "void f(int n) {\n"
                '    if (n > 0) { // <!(T,"n > 0, n=1") ,( F , "f(0)")>\n'
                "        f(n - 1);\n    }\n}\n"
                "int main() {\n    f(1);\n    return 0;\n}\n"
            ),
            "c++",
        ),
    ],
    ids=["python", "c++"],
)
def test_tuple_marker_sets_value_hints(code: str, language: str):
    registry = code_snippet_to_registry(code, language=language)

    [condition] = [action for action in registry.all_actions() if action.is_condition]

    assert condition.annotation is not None
    assert condition.annotation.marker == '<! (T, "n > 0, n=1"), (F, "f(0)") >'
    assert [(value.bool_value, value.hint) for value in condition.values] == [
        (True, "n > 0, n=1"),
        (False, "f(0)"),
    ]


def test_null_markers_bind_to_calls_on_their_line():
    registry = code_snippet_to_registry(
        textwrap.dedent(
            """
            def f(n):
                if f(n - 1) > 0:  # <! (-, "f(1)") >
                    return 1
                if n > 0:  # <! (T, "n=2"), (F, "n=1") >
                    return n
                return 0
            print(f(2))  # <! (-, "f(2)") >
            """
        )
    )
    code = registry.code

    # Строки - в коде, перегенерированном MT.
    annotated = {
        (code.code_line_number_by_id(action.parent.ast_id), action.rule.role): [
            (value.bool_value, value.hint) for value in action.values
        ]
        for action in registry.all_actions()
        if action.annotation is not None
    }

    # На строке с условием-вызовом маркер с «-» размечает вызов, а не условие. Подсказки
    # END расставляет трасса, до неё у END только значения.
    assert annotated == {
        (2, "BEGIN"): [(None, "f(1)")],
        (2, "END"): [(None, "")],
        (4, "first_cond"): [(True, "n=2"), (False, "n=1")],
        (9, "BEGIN"): [(None, "f(2)")],
        (9, "END"): [(None, "")],
    }


def test_several_markers_bind_condition_and_calls_selected_by_target():
    registry = code_snippet_to_registry(
        textwrap.dedent(
            """
            def fib(n):
                if n < 2:  # <! TT >
                    return n
                return fib(n - 1) + fib(n - 2)  # <! fib#2: (-, "fib(0)") > <! fib#1: (-, "fib(1)") >
            def g(x):
                return x
            if g(fib(2)) > 0:  # <! T > <! fib: (-, "fib(2)") > <! g: (-, "g(1)") >
                pass
            """
        )
    )
    code = registry.code

    def text_position(action) -> int:
        tokens = code.token_index_range(action.parent.ast_id)
        assert tokens is not None
        return tokens[0]

    # BEGIN размеченных вызовов каждой строки - в порядке текста.
    begins: dict[int | None, list[str | None]] = {}
    conditions: dict[int | None, str] = {}
    for action in sorted(registry.all_actions(), key=text_position):
        if action.annotation is None:
            continue
        line = code.code_line_number_by_id(action.parent.ast_id)
        if action.is_condition:
            conditions[line] = action.annotation.marker
        elif action.rule.role == "BEGIN":
            begins.setdefault(line, []).extend(value.hint for value in action.values)

    # Строки - в коде, перегенерированном MT.
    assert conditions == {2: "<! TT >", 11: "<! T >"}
    assert begins == {4: ["fib(1)", "fib(0)"], 11: ["g(1)", "fib(2)"]}


def test_markers_bind_in_code_with_crlf_line_endings():
    code = 'def f(n):\r\n    return n\r\nf(1)  # <! (-, "f(1)") >\r\nf(2)  # <! (-, "f(2)") >\r\n'

    registry = code_snippet_to_registry(code)

    begin_hints = sorted(
        value.hint
        for action in registry.all_actions()
        if action.annotation is not None and action.rule.role == "BEGIN"
        for value in action.values
    )
    assert begin_hints == ["f(1)", "f(2)"]


@pytest.mark.parametrize(
    ("code", "message"),
    [
        pytest.param(
            'def f():\n    return 1\nx = f()  # <! (T, "a"), (-, "b") >\n',
            r"<! \(T, \"a\"\), \(-, \"b\"\) > — нельзя смешивать T/F и -",
            id="mixed",
        ),
        pytest.param(
            'x = 1  # <! (-, "a") >\n',
            r"— к комментарию не привязан вызов функции",
            id="no-call",
        ),
        pytest.param(
            'print(1)  # <! (-, "p") >\n',
            r"— к комментарию не привязан вызов функции",
            id="library-call",
        ),
        pytest.param(
            'def f(x):\n    return x\ny = f(1) + f(2)  # <! (-, "a") >\n',
            r"— на строке несколько вызовов функций, разметка неоднозначна: "
            r"укажите цель \(f#1, f#2\)",
            id="ambiguous",
        ),
        pytest.param(
            'def f(x):\n    return x\ny = f(1) + f(2)  # <! f: (-, "a") >\n',
            r"<! f: \(-, \"a\"\) > — на строке несколько вызовов f, укажите номер: f#1, f#2",
            id="ambiguous-name",
        ),
        pytest.param(
            'def f(x):\n    return x\ny = f(1) + f(2)  # <! f#3: (-, "a") >\n',
            r"— на строке вызовов f: 2, 3-го нет",
            id="missing-index",
        ),
        pytest.param(
            'def f(x):\n    return x\ny = f(1)  # <! g: (-, "a") >\n',
            r"— к комментарию не привязан вызов функции g",
            id="unknown-name",
        ),
        pytest.param(
            'def f(x):\n    return x\nwhile f(0):  # <! f: F >\n    pass\n',
            r"<! f: F > — цель задаётся только у разметки вызова",
            id="condition-target",
        ),
        pytest.param(
            'def f(x):\n    return x\ny = f(1) + f(2)  # <! f#1: (-, "a") > <! f#1: (-, "b") >\n',
            r"<! f#1: \(-, \"b\"\) > — вызов уже размечен",
            id="duplicate-call",
        ),
        pytest.param(
            "x = 1\nwhile x:  # <! TF > <! F >\n    x = 0\n",
            r"<! F > — условие уже размечено",
            id="duplicate-condition",
        ),
    ],
)
def test_null_marker_errors_stop_situation_generation(code: str, message: str):
    with pytest.raises(ValueError, match=message):
        code_snippet_to_registry(code)


@pytest.mark.parametrize(
    ("code", "language", "message"),
    [
        pytest.param(
            "if x:\n    pass\nelse:  # <! F >\n    pass\n",
            "python",
            r"<! F > — к комментарию не привязано условие",
            id="own-line-comment",
        ),
        pytest.param(
            """
            int main() {
                int a = 1;
                int x = 0;
                if (a) x = 1; // <! T >
                return 0;
            }
            """,
            "c++",
            r"<! T > — к комментарию не привязано условие",
            id="owner-in-body",
        ),
        pytest.param(
            "x = 1  # <! TT >\n",
            "python",
            r"<! TT > — к комментарию не привязано условие",
            id="no-condition-above",
        ),
        pytest.param(
            "while x:  # <! TX >\n    x = 0\n",
            "python",
            r"строка 1: некорректная разметка <! TX >",
            id="malformed",
        ),
        pytest.param(
            'while x:  # <! (T, "a") (F, "b") >\n    x = 0\n',
            "python",
            r"строка 1: некорректная разметка .*: ожидалось «,», а не «\(»",
            id="malformed-tuples",
        ),
    ],
)
def test_marker_errors_stop_situation_generation(code: str, language: str, message: str):
    with pytest.raises(ValueError, match=message):
        code_snippet_to_registry(textwrap.dedent(code), language=language)


@pytest.mark.parametrize(
    ("code", "language", "kept_comment"),
    [
        ("x = 3\nwhile x > 0:  # <! TF >\n    x -= 1  # step\n", "python", "# step"),
        (
            (
                "int main() {\n    int x = 3;\n    while (x > 0) { // <! TF >\n"
                "        x--; // step\n    }\n    return 0;\n}\n"
            ),
            "c++",
            "// step",
        ),
    ],
    ids=["python", "c++"],
)
def test_markers_are_hidden_from_task_code(code: str, language: str, kept_comment: str):
    manager = prepare_code(code, language)  # type: ignore[arg-type]

    task_code = strip_value_markers(manager)
    rendered = [
        entity.value
        for line in prepare_html_context(manager)["lines"]
        for entity in line
        if isinstance(entity, Token)
    ]

    assert "<!" not in task_code
    assert kept_comment in task_code
    assert all(line == line.rstrip() for line in task_code.splitlines())
    assert not [value for value in rendered if "<!" in value]
    assert kept_comment in rendered
