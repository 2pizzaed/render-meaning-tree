import textwrap

import pytest

from src.generator.utilities import code_snippet_to_registry

pytestmark = pytest.mark.filterwarnings("ignore:No construct declaration found")


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
    ],
)
def test_marker_errors_stop_situation_generation(code: str, language: str, message: str):
    with pytest.raises(ValueError, match=message):
        code_snippet_to_registry(textwrap.dedent(code), language=language)
