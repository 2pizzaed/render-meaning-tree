import textwrap
from pathlib import Path
from typing import cast

import pytest

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
)
from src.generator.utilities import code_snippet_to_pipeline
from src.model.situation import Action, TraceAct
from src.tpg_domain import ReasoningResult, solve_reasoning
from test.helpers import (
    line_actions,
    open_file_and_wait,
    pipeline_debug_json_artifacts,
    pipeline_to_loqi_files,
    render_trace_acts_artifacts,
    require_line_action,
    resolve_project_root,
    restore_trace_from_loqi,
    should_open_test_artifacts,
    trace_acts_from_loqi,
)

TREE_NAME = "findCorrect"
ActionValuePatches = dict[tuple[int, int], list[bool]]
SequenceCase = tuple[
    str,
    str,
    dict[int, list[str]] | None,
    list[tuple[int, int]],
    str,
    ActionValuePatches | None,
]

# TODO: данные тестов пока не валидны!
SEQUENCE_CASES: list[tuple[object, ...]] = [
    (
        "python",
        """
        if x == 1:
            x = 1
        elif x == 2:
            x = 2
        elif x == 3:
            x = 3
        else:
            x = 4
        y = x
        """,
        {
            1: ["first", "first_cond"],
            2: ["if_branch", "first"],
            3: ["next_cond"],
            4: ["if_branch", "first"],
            5: ["next_cond"],
            6: ["if_branch", "first"],
            8: ["else_branch", "first"],
            9: ["next"],
        },
        [(1, 1), (3, 0), (5, 0), (8, 1), (9, 0)],
        "python_if_elseif_elseif_else.loqi",
        {
            (1, 1): [False],
            (3, 0): [False],
            (5, 0): [False],
        },
    ),
    (
        "python",
        """
        if x == 1:
            x = 1
        elif x == 2:
            x = 2
        elif x == 3:
            x = 3
        y = x
        """,
        {
            1: ["first", "first_cond"],
            2: ["if_branch", "first"],
            3: ["next_cond"],
            4: ["if_branch", "first"],
            5: ["next_cond"],
            6: ["if_branch", "first"],
            7: ["next"],
        },
        [(1, 1), (3, 0), (5, 0), (6, 1), (7, 0)],
        "python_if_elseif_elseif.loqi",
        {
            (1, 1): [False],
            (3, 0): [False],
            (5, 0): [True],
        },
    ),
    (
        "python",
        """
        if x == 1:
            x = 1
        y = x
        """,
        {
            1: ["first", "first_cond"],
            2: ["if_branch", "first"],
            3: ["next"],
        },
        [(1, 1), (2, 1), (3, 0)],
        "python_if_only.loqi",
    ),
    (
        "python",
        """
        for value in values:
            total = total + value
        result = total
        """,
        {
            1: ["first", "cond", "init"],
            2: ["body", "first"],
            3: ["next"],
        },
        [(1, 2), (1, 1), (2, 1), (1, 1), (2, 1), (1, 1), (3, 0)],
        "python_for_each.loqi",
    ),
    (
        "python",
        """
        for i in range(3):
            total = total + i
        result = total
        """,
        {
            1: ["first", "cond", "init"],
            2: ["body", "first"],
            3: ["next"],
        },
        [(1, 2), (1, 1), (2, 1), (1, 1), (2, 1), (1, 1), (3, 0)],
        "python_for_range.loqi",
    ),
    (
        "python",
        """
        while flag:
            break
        x = 1
        """,
        {
            1: ["first", "cond"],
            2: ["body", "first"],
            3: ["next"],
        },
        [(1, 1), (2, 1), (1, 1), (2, 1), (1, 1), (3, 0)],
        "python_break.loqi",
    ),
    (
        "python",
        """
        while flag:
            continue
        x = 1
        """,
        {
            1: ["first", "cond"],
            2: ["body", "first"],
            3: ["next"],
        },
        [(1, 1), (2, 1), (1, 1), (2, 1), (1, 1), (3, 0)],
        "python_continue.loqi",
    ),
    (
        "python",
        """
        def g(x):
            return x + 1

        def f(x):
            return g(x)

        result = f(1)
        """,
        {
            1: ["func"],
            2: ["func_body", "first"],
            5: ["func"],
            6: ["func_body", "first"],
        },
        [(6, 1), (2, 1)],
        "python_sequential_function_calls.loqi",
    ),
    (
        "c++",
        """
        int x = 2;
        if (x == 1) {
            x = 10;
        } else if (x == 2) {
            x = 20;
        } else if (x == 3) {
            x = 30;
        } else {
            x = 40;
        }
        int y = x;
        """,
        {
            1: ["first"],
            2: ["next", "first_cond"],
            3: ["if_branch"],
            4: ["first"],
            6: ["next_cond"],
            7: ["if_branch"],
            8: ["first"],
            10: ["next_cond"],
            11: ["if_branch"],
            12: ["first"],
        },
        [(1, 0), (2, 1), (6, 0), (10, 0), (16, 0), (18, 0)],
        "cpp_if_elseif_elseif_else.loqi",
        {
            (2, 1): [False],
            (6, 0): [False],
            (10, 0): [False],
        },
    ),
    (
        "c++",
        """
        int x = 2;
        if (x == 1) {
            x = 10;
        } else if (x == 2) {
            x = 20;
        } else if (x == 3) {
            x = 30;
        }
        int y = x;
        """,
        {
            1: ["first"],
            2: ["next", "first_cond"],
            3: ["if_branch"],
            4: ["first"],
            6: ["next_cond"],
            7: ["if_branch"],
            8: ["first"],
            10: ["next_cond"],
        },
        [(1, 0), (2, 1), (6, 0), (10, 0), (12, 0), (14, 0)],
        "cpp_if_elseif_elseif.loqi",
        {
            (2, 1): [False],
            (6, 0): [False],
            (10, 0): [True],
        },
    ),
    (
        "c++",
        """
        int x = 1;
        if (x == 1) {
            x = 10;
        }
        int y = x;
        """,
        {
            1: ["first"],
            2: ["next", "first_cond"],
            3: ["if_branch"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 1), (4, 0), (6, 0)],
        "cpp_if_only.loqi",
    ),
    (
        "c++",
        """
        int total = 0;
        for (int value : values) {
            total = total + value;
        }
        int result = total;
        """,
        {
            1: ["first"],
            2: ["next", "cond", "init"],
            3: ["body"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 2), (2, 1), (4, 0), (2, 1), (4, 0), (2, 1), (6, 0)],
        "cpp_for_each.loqi",
    ),
    (
        "c++",
        """
        int total = 0;
        for (int i = 0; i < 3; i = i + 1) {
            total = total + i;
        }
        int result = total;
        """,
        None,
        [
            (1, 0),
            (2, 1),
            (2, 2),
            (4, 0),
            (2, 3),
            (2, 2),
            (4, 0),
            (2, 3),
            (2, 2),
            (6, 0),
        ],
        "cpp_general_for.loqi",
    ),
    (
        "c++",
        """
        int total = 0;
        int i = 0;
        for (; i < 3; i = i + 1) {
            total = total + i;
        }
        int result = total;
        """,
        None,
        [
            (1, 0),
            (2, 0),
            (3, 1),
            (5, 0),
            (3, 2),
            (3, 1),
            (5, 0),
            (3, 2),
            (3, 1),
            (7, 0),
        ],
        "cpp_general_for_missing_init.loqi",
    ),
    (
        "c++",
        """
        bool flag = true;
        while (flag) {
            break;
        }
        int x = 1;
        """,
        {
            1: ["first"],
            2: ["next", "cond"],
            3: ["body"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 1), (4, 0), (2, 1), (4, 0), (2, 1), (6, 0)],
        "cpp_break.loqi",
    ),
    (
        "c++",
        """
        bool flag = true;
        while (flag) {
            continue;
        }
        int x = 1;
        """,
        {
            1: ["first"],
            2: ["next", "cond"],
            3: ["body"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 1), (4, 0), (2, 1), (4, 0), (2, 1), (6, 0)],
        "cpp_continue.loqi",
    ),
    (
        "c++",
        """
        int g(int x) {
            return x + 1;
        }
        int f(int x) {
            return g(x);
        }
        int main() {
            int result = f(1);
            return result;
        }
        """,
        {
            1: ["func"],
            2: ["func_body"],
            3: ["first"],
            5: ["func"],
            6: ["func_body"],
            7: ["first"],
            10: ["func_body"],
            11: ["first"],
            12: ["next"],
        },
        [(7, 0), (3, 0), (12, 0)],
        "cpp_sequential_function_calls.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int x = 2;
                if (x == 1) {
                    x = 10;
                } else if (x == 2) {
                    x = 20;
                } else if (x == 3) {
                    x = 30;
                } else {
                    x = 40;
                }
                int y = x;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "first_cond", "if_branch"],
            3: ["first"],
            5: ["next_cond", "if_branch"],
            6: ["first"],
            8: ["next_cond", "if_branch"],
            9: ["first"],
            11: ["else_branch"],
            12: ["first"],
            14: ["next"],
        },
        [(1, 0), (2, 1), (5, 0), (8, 0), (12, 0), (14, 0)],
        "java_if_elseif_elseif_else.loqi",
        {
            (2, 1): [False],
            (5, 0): [False],
            (8, 0): [False],
        },
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int x = 2;
                if (x == 1) {
                    x = 10;
                } else if (x == 2) {
                    x = 20;
                } else if (x == 3) {
                    x = 30;
                }
                int y = x;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "first_cond", "if_branch"],
            3: ["first"],
            5: ["next_cond", "if_branch"],
            6: ["first"],
            8: ["next_cond", "if_branch"],
            9: ["first"],
            11: ["next"],
        },
        [(1, 0), (2, 1), (5, 0), (8, 0), (9, 0), (11, 0)],
        "java_if_elseif_elseif.loqi",
        {
            (2, 1): [False],
            (5, 0): [False],
            (8, 0): [True],
        },
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int x = 1;
                if (x == 1) {
                    x = 10;
                }
                int y = x;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "first_cond", "if_branch"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 1), (3, 0), (5, 0)],
        "java_if_only.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int total = 0;
                for (int value : values) {
                    total = total + value;
                }
                int result = total;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "cond", "init", "body"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 2), (2, 1), (3, 0), (2, 1), (3, 0), (2, 1), (5, 0)],
        "java_for_each.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int total = 0;
                for (int i = 0; i < 3; i = i + 1) {
                    total = total + i;
                }
                int result = total;
            }
        }
        """,
        None,
        [
            (1, 0),
            (2, 1),
            (2, 2),
            (3, 0),
            (2, 3),
            (2, 2),
            (3, 0),
            (2, 3),
            (2, 2),
            (5, 0),
        ],
        "java_general_for.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int total = 0;
                int i = 0;
                for (; i < 3; i = i + 1) {
                    total = total + i;
                }
                int result = total;
            }
        }
        """,
        None,
        [
            (1, 0),
            (2, 0),
            (3, 1),
            (4, 0),
            (3, 2),
            (3, 1),
            (4, 0),
            (3, 2),
            (3, 1),
            (6, 0),
        ],
        "java_general_for_missing_init.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                boolean flag = true;
                while (flag) {
                    break;
                }
                int x = 1;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "cond", "body"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 1), (3, 0), (2, 1), (3, 0), (2, 1), (5, 0)],
        "java_break.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                boolean flag = true;
                while (flag) {
                    continue;
                }
                int x = 1;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "cond", "body"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 1), (3, 0), (2, 1), (3, 0), (2, 1), (5, 0)],
        "java_continue.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static int g(int x) {
                return x + 1;
            }
            static int f(int x) {
                return g(x);
            }
            static void main(String[] args) {
                int result = f(1);
            }
        }
        """,
        {
            1: ["func", "func_body"],
            2: ["first"],
            5: ["func", "func_body"],
            6: ["first"],
            9: ["func_body"],
            10: ["first"],
        },
        [(6, 0), (2, 0)],
        "java_sequential_function_calls.loqi",
    ),
    (
        "python",
        """
        if True:
            x = 1
        else:
            x = 2
        y = 3
        """,
        {
            1: ["first", "first_cond"],
            2: ["if_branch", "first"],
            4: ["else_branch", "first"],
            5: ["next"],
        },
        [(1, 1), (2, 1), (5, 0)],
        "python_if_else.loqi",
    ),
    (
        "python",
        """
        i = 0
        while i < 2:
            i = i + 1
        x = i
        """,
        {
            1: ["first"],
            2: ["next", "cond"],
            3: ["body", "first"],
            4: ["next"],
        },
        [(1, 0), (2, 1), (3, 1), (2, 1), (3, 1), (2, 1), (4, 0)],
        "python_while.loqi",
    ),
    (
        "python",
        """
        def add(a, b):
            return a + b

        x = add(1, 2)
        """,
        {
            1: ["func"],
            2: ["func_body", "first"],
            5: ["first"],
        },
        [(2, 1)],
        "python_function_call.loqi",
    ),
    (
        "c++",
        """
        bool cond = true;
        if (cond) {
            int x = 1;
        }
        int y = 0;
        """,
        {
            1: ["first"],
            2: ["next", "first_cond"],
            3: ["if_branch"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 1), (4, 0), (6, 0)],
        "cpp_if.loqi",
    ),
    (
        "c++",
        """
        bool cond = true;
        while (cond) {
            cond = false;
        }
        """,
        {
            1: ["first"],
            2: ["next", "cond"],
            3: ["body"],
        },
        [(1, 0), (2, 1), (4, 0), (2, 1), (4, 0), (2, 1)],
        "cpp_while.loqi",
    ),
    (
        "c++",
        """
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int x = add(1, 2);
            return x;
        }
        """,
        {
            1: ["func"],
            2: ["func_body"],
            3: ["first"],
            6: ["func_body"],
            7: ["first"],
            8: ["next"],
        },
        [(3, 0), (8, 0)],
        "cpp_function_call.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int x = 0;
                if (x == 0) {
                    x = 1;
                }
                x = 2;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "first_cond", "if_branch"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 1), (3, 0), (5, 0)],
        "java_if.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static void main(String[] args) {
                int i = 0;
                while (i < 2) {
                    i = i + 1;
                }
                int x = i;
            }
        }
        """,
        {
            1: ["first"],
            2: ["next", "cond", "body"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 1), (3, 0), (2, 1), (3, 0), (2, 1), (5, 0)],
        "java_while.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static int add(int a, int b) {
                return a + b;
            }
            static void main(String[] args) {
                int x = add(1, 2);
            }
        }
        """,
        {
            1: ["func", "func_body"],
            2: ["first"],
            5: ["func_body"],
            6: ["first"],
        },
        [(2, 0)],
        "java_function_call.loqi",
    ),
]


def _normalize_sequence_case(case: tuple[object, ...]) -> SequenceCase:
    if len(case) == 5:
        language, code, expected_roles, expected_actions, loqi_filename = case
        return (
            cast(str, language),
            cast(str, code),
            cast(dict[int, list[str]] | None, expected_roles),
            cast(list[tuple[int, int]], expected_actions),
            cast(str, loqi_filename),
            None,
        )

    language, code, expected_roles, expected_actions, loqi_filename, value_patches = (
        case
    )
    return (
        cast(str, language),
        cast(str, code),
        cast(dict[int, list[str]] | None, expected_roles),
        cast(list[tuple[int, int]], expected_actions),
        cast(str, loqi_filename),
        cast(ActionValuePatches | None, value_patches),
    )


SEQUENCE_CASE_PARAMS: list[SequenceCase] = [
    _normalize_sequence_case(case) for case in SEQUENCE_CASES
]


# -- Tests --------------------------------------------------------------------


def test_plain_statements(tmp_path: Path):
    loqi_filename = "plain_statements.loqi"
    code = textwrap.dedent("""
        x = 1
        y = 2
        a = x + y
    """)
    pipeline = code_snippet_to_pipeline(code, language="python")
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]

    assert (
        registry.get_construct_for(
            pipeline.code.ast.find_paths_by_type("program_entry_point")[0].id
        )
        is not None
    )

    expected_actions = [
        require_line_action(registry, 1, action_index=0),
        require_line_action(registry, 2, action_index=0),
        require_line_action(registry, 3, action_index=0),
    ]

    assert [action.rule.role for action in line_actions(registry, 1)] == ["first"]
    assert [action.rule.role for action in line_actions(registry, 2)] == ["next"]
    assert [action.rule.role for action in line_actions(registry, 3)] == ["next"]
    first_node = pipeline.code.line_number_to_ast_node(1)
    second_node = pipeline.code.line_number_to_ast_node(2)
    third_node = pipeline.code.line_number_to_ast_node(3)
    assert first_node is not None
    assert second_node is not None
    assert third_node is not None
    assert [action.ast_id for action in expected_actions] == [
        first_node.id,
        second_node.id,
        third_node.id,
    ]

    registry.variables["P"] = registry.trace_acts[0]
    pipeline_debug_json_artifacts(
        tmp_path,
        pipeline,
        filename_stem=Path(loqi_filename).stem,
    )

    for expected_action in expected_actions:
        solve_output = _advance_until_expected_action(
            tmp_path, pipeline, expected_action, loqi_filename=loqi_filename
        )
        assert solve_output.variables["T"].startswith("object transition_")

    _write_final_loqi_trace_artifacts(
        tmp_path,
        pipeline,
        loqi_filename=loqi_filename,
    )
    open_file_and_wait(tmp_path / loqi_filename, enabled=should_open_test_artifacts())


@pytest.mark.parametrize(
    (
        "language",
        "code",
        "expected_roles",
        "expected_actions",
        "loqi_filename",
        "value_patches",
    ),
    SEQUENCE_CASE_PARAMS,
    ids=[Path(case[4]).stem for case in SEQUENCE_CASE_PARAMS],
)
def test_solve_tree_sequences(
    tmp_path: Path,
    *,
    language: str,
    code: str,
    expected_roles: dict[int, list[str]] | None,
    expected_actions: list[tuple[int, int]],
    loqi_filename: str,
    value_patches: ActionValuePatches | None,
):
    pipeline, registry = _build_registry(code, language=language)
    _apply_action_value_patches(registry, value_patches)
    pipeline_debug_json_artifacts(
        tmp_path,
        pipeline,
        filename_stem=Path(loqi_filename).stem,
    )
    _assert_line_roles(registry, expected_roles)
    _assert_solve_sequence(
        tmp_path,
        code=code,
        language=language,
        expected_actions=expected_actions,
        loqi_filename=loqi_filename,
        value_patches=value_patches,
    )


def test_line_actions_excludes_transparent_by_default() -> None:
    _pipeline, registry = _build_registry(
        """
        if True:
            x = 1
        """,
        language="python",
    )

    assert [action.rule.role for action in line_actions(registry, 1)] == [
        "first",
        "first_cond",
    ]
    assert [
        action.rule.role
        for action in line_actions(registry, 1, include_transparent=True)
    ] == [
        "BEGIN",
        "END",
        "first",
        "first_cond",
    ]


# -- Helpers ------------------------------------------------------------------


def _build_registry(
    code: str, *, language: str
) -> tuple[
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
]:
    pipeline = code_snippet_to_pipeline(textwrap.dedent(code), language=language)
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]
    registry.variables["P"] = registry.trace_acts[0]
    return pipeline, registry


def _assert_line_roles(
    registry: SituationDomainDataRegistry,
    expectations: dict[int, list[str]] | None,
    *,
    include_transparent: bool = False,
) -> None:
    if expectations is None:
        return
    for line_number, expected_roles in expectations.items():
        assert [
            action.rule.role
            for action in line_actions(
                registry,
                line_number,
                include_transparent=include_transparent,
            )
        ] == expected_roles


def _apply_action_value_patches(
    registry: SituationDomainDataRegistry,
    patches: ActionValuePatches | None,
) -> None:
    if patches is None:
        return
    for (line_number, action_index), values in patches.items():
        require_line_action(
            registry,
            line_number,
            action_index=action_index,
        ).values = values.copy()


def _assert_solve_sequence(
    tmp_path: Path,
    *,
    code: str,
    language: str,
    expected_actions: list[tuple[int, int]],
    loqi_filename: str,
    value_patches: ActionValuePatches | None = None,
) -> None:
    pipeline, registry = _build_registry(code, language=language)
    _apply_action_value_patches(registry, value_patches)
    pipeline_debug_json_artifacts(
        tmp_path,
        pipeline,
        filename_stem=Path(loqi_filename).stem,
    )
    end_action = _require_root_end_action(pipeline, registry)
    actions = [
        require_line_action(registry, line_number, action_index=action_index)
        for line_number, action_index in expected_actions
    ]
    actions.append(end_action)

    for expected_action in actions:
        solve_output = _advance_until_expected_action(
            tmp_path, pipeline, expected_action, loqi_filename=loqi_filename
        )
        if expected_action is not end_action:
            assert solve_output.variables["T"].startswith("object transition_")

    _write_final_loqi_trace_artifacts(
        tmp_path,
        pipeline,
        loqi_filename=loqi_filename,
    )


def _require_root_end_action(
    pipeline: DomainDataGeneratorPipeline,
    registry: SituationDomainDataRegistry,
) -> Action:
    entry_point_id = pipeline.code.ast.find_paths_by_type("program_entry_point")[0].id
    entry_point = pipeline.get_construct_for(entry_point_id)
    assert entry_point is not None
    return next(
        action
        for action in registry.get_related_actions(entry_point)
        if action.rule.role == "END"
    )


def _write_final_loqi_trace_artifacts(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    loqi_filename: str,
) -> Path:
    _serializer, loqi_file = pipeline_to_loqi_files(
        tmp_path,
        pipeline,
        filename=loqi_filename,
    )[0]
    loqi_text = loqi_file.read_text(encoding="utf-8")
    trace_acts = trace_acts_from_loqi(loqi_text, pipeline)
    render_trace_acts_artifacts(
        tmp_path,
        trace_acts,
        filename_stem=f"{Path(loqi_filename).stem}-trace-acts",
    )
    pipeline_debug_json_artifacts(
        tmp_path,
        pipeline,
        filename_stem=Path(loqi_filename).stem,
    )
    return loqi_file


def _advance_until_expected_action(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    expected_action: Action,
    *,
    loqi_filename: str,
) -> ReasoningResult:
    serializer, _ = pipeline_to_loqi_files(
        tmp_path,
        pipeline,
        filename=loqi_filename,
    )[0]
    expected_action_name = serializer.object_name(expected_action)
    assert expected_action_name is not None

    previous_trace_length = len(pipeline.registry.trace_acts)
    last_output: ReasoningResult | None = None
    solve_output = _solve_once(
        tmp_path,
        pipeline,
        loqi_filename=loqi_filename,
    )
    last_output = solve_output
    current_trace_length = len(pipeline.registry.trace_acts)
    if current_trace_length <= previous_trace_length:
        _write_trace_artifacts(
            tmp_path,
            f"{Path(loqi_filename).stem}-failtrace-{len(pipeline.registry.trace_acts) - 1:02d}",
            pipeline.registry.trace_acts,
            _require_specific_domain(solve_output),
        )
        raise AssertionError(
            f"Trace did not grow while waiting for {expected_action_name!r} "
        )
    previous_trace_length = current_trace_length
    actual_trace_act = pipeline.registry.variables.get("P")
    actual_action = (
        actual_trace_act.action if isinstance(actual_trace_act, TraceAct) else None
    )
    if actual_action is expected_action:
        return solve_output

    _write_trace_artifacts(
        tmp_path,
        f"{Path(loqi_filename).stem}-failtrace-{len(pipeline.registry.trace_acts) - 1:02d}",
        pipeline.registry.trace_acts,
        _require_specific_domain(last_output),
    )
    actual_p_name = (
        serializer.object_name(actual_action) if actual_action is not None else None
    )
    raise AssertionError(
        f"Did not reach expected action {expected_action_name!r}; "
        f"last P={actual_p_name!r}"
    )


def _solve_once(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    loqi_filename: str,
) -> ReasoningResult:
    _serializer, loqi_file = pipeline_to_loqi_files(
        tmp_path,
        pipeline,
        filename=loqi_filename,
    )[0]
    loqi_text = loqi_file.read_text(encoding="utf-8")
    reasoner_output_file = tmp_path / "reasoner_output.txt"
    with reasoner_output_file.open("a", encoding="utf-8") as reasoner_out:
        solve_output = solve_reasoning(
            resolve_project_root() / "domain",
            loqi_file,
            tree=TREE_NAME,
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=45,
            reasoner_output_stream=reasoner_out,
        )

    if solve_output is None:
        _write_trace_artifacts(
            tmp_path,
            f"{Path(loqi_filename).stem}-failtrace-{len(pipeline.registry.trace_acts) - 1:02d}",
            pipeline.registry.trace_acts,
            loqi_text,
        )
    assert solve_output is not None
    if solve_output.trace is not None:
        loqi_file.with_suffix(".trace.txt").write_text(
            str(solve_output.trace), encoding="utf-8"
        )
    exported_loqi = solve_output.artifacts.get("specificDomain")
    if solve_output.result is not True or solve_output.exceptions:
        _write_trace_artifacts(
            tmp_path,
            f"{Path(loqi_filename).stem}-failtrace-{len(pipeline.registry.trace_acts) - 1:02d}",
            restore_trace_from_loqi(
                exported_loqi or loqi_text, pipeline, replace_existing=False
            )[0],
            exported_loqi if isinstance(exported_loqi, str) else loqi_text,
        )
    assert solve_output.result is True
    assert not solve_output.exceptions, str(solve_output)
    assert isinstance(exported_loqi, str)

    trace_acts, trace_state = restore_trace_from_loqi(exported_loqi, pipeline)
    assert trace_state is not None
    assert trace_acts

    assert pipeline.registry.variables["P"] is trace_acts[-1]
    return solve_output


def _require_specific_domain(result: ReasoningResult | None) -> str:
    assert result is not None
    exported_loqi = result.artifacts.get("specificDomain")
    assert isinstance(exported_loqi, str)
    return exported_loqi


def _write_trace_artifacts(
    tmp_path: Path,
    stem: str,
    trace_acts: list[TraceAct],
    loqi_content: str,
) -> None:
    render_trace_acts_artifacts(tmp_path, trace_acts, filename_stem=stem)
    (tmp_path / f"{stem}.loqi").write_text(loqi_content, encoding="utf-8", newline="")
