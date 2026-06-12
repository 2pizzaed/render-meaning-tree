import textwrap
from pathlib import Path

import pytest

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
)
from src.generator.utilities import code_snippet_to_pipeline
from src.model.rules import TransitionDeclaration
from src.model.situation import Action
from src.tpg_domain import ReasoningResult, solve_reasoning
from test.helpers import (
    add_trace_act_for_action,
    line_actions,
    open_file_and_wait,
    pipeline_to_loqi_files,
    require_line_action,
    resolve_project_root,
    should_open_test_artifacts,
)

TREE_NAME = "findCorrect"

SEQUENCE_CASES = [
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
            1: ["BEGIN", "END", "first", "first_cond"],
            2: ["BEGIN", "END", "if_branch", "first"],
            4: ["BEGIN", "END", "else_branch", "first"],
            5: ["next"],
        },
        [(1, 2), (5, 0)],
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
            2: ["BEGIN", "END", "next", "cond"],
            3: ["BEGIN", "END", "body", "first"],
            4: ["next"],
        },
        [(1, 0), (2, 2), (4, 0)],
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
            1: ["first"],
            2: ["BEGIN", "END", "first"],
            5: ["next"],
        },
        [(1, 0), (5, 0)],
        "python_function_call.loqi",
    ),
    (
        "python",
        """
        def fact(n):
            if n <= 1:
                return 1
            return n * fact(n - 1)

        x = fact(3)
        """,
        {
            1: ["first"],
            2: ["BEGIN", "END", "BEGIN", "END", "first", "first_cond"],
            3: ["BEGIN", "END", "if_branch", "first"],
            4: ["next"],
            7: ["next"],
        },
        [(1, 0), (7, 0)],
        "python_recursion.loqi",
    ),
    (
        "c++",
        """
        int main() {
            bool cond = true;
            if (cond) {
                int x = 1;
            }
            return 0;
        }
        """,
        {
            1: ["first"],
            2: ["BEGIN", "END", "next", "first_cond"],
            3: ["BEGIN", "END", "if_branch"],
            4: ["first"],
            6: ["next"],
        },
        [(1, 0), (2, 2), (6, 0)],
        "cpp_if.loqi",
    ),
    (
        "c++",
        """
        int main() {
            bool cond = true;
            while (cond) {
                return 0;
            }
        }
        """,
        {
            1: ["first"],
            2: ["BEGIN", "END", "next", "cond"],
            3: ["BEGIN", "END", "body"],
            4: ["first"],
        },
        [(1, 0), (2, 2)],
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
            1: ["first"],
            2: ["next"],
        },
        [(1, 0), (2, 0)],
        "cpp_function_call.loqi",
    ),
    (
        "c++",
        """
        int fact(int n) {
            if (n) {
                return n * fact(n - 1);
            }
            return 1;
        }
        int main() {
            return fact(3);
        }
        """,
        {
            1: ["first"],
        },
        [(1, 0)],
        "cpp_recursion.loqi",
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
            2: ["BEGIN", "END", "next", "first_cond", "BEGIN", "END", "if_branch"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 2), (5, 0)],
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
            2: ["BEGIN", "END", "next", "cond", "BEGIN", "END", "body"],
            3: ["first"],
            5: ["next"],
        },
        [(1, 0), (2, 2), (5, 0)],
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
            1: ["first"],
        },
        [(1, 0)],
        "java_function_call.loqi",
    ),
    (
        "java",
        """
        public class Main {
            static int fact(int n) {
                if (n <= 1) {
                    return 1;
                }
                return n * fact(n - 1);
            }
            static void main(String[] args) {
                int x = fact(3);
            }
        }
        """,
        {
            1: ["first"],
        },
        [(1, 0)],
        "java_recursion.loqi",
    ),
]


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

    for expected_action in expected_actions:
        solve_output, transition = _solve_next_step(
            tmp_path, pipeline, expected_action, loqi_filename=loqi_filename
        )
        add_trace_act_for_action(pipeline, expected_action, transition=transition)
        assert solve_output.variables["T"].startswith("object transition_")

    open_file_and_wait(tmp_path / loqi_filename, enabled=should_open_test_artifacts())


def _build_registry(code: str, *, language: str) -> tuple[
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
    expectations: dict[int, list[str]],
) -> None:
    for line_number, expected_roles in expectations.items():
        assert [action.rule.role for action in line_actions(registry, line_number)] == (
            expected_roles
        )


def _assert_solve_sequence(
    tmp_path: Path,
    *,
    code: str,
    language: str,
    expected_actions: list[tuple[int, int]],
    loqi_filename: str,
) -> None:
    pipeline, registry = _build_registry(code, language=language)
    actions = [
        require_line_action(registry, line_number, action_index=action_index)
        for line_number, action_index in expected_actions
    ]

    for expected_action in actions:
        solve_output, transition = _solve_next_step(
            tmp_path, pipeline, expected_action, loqi_filename=loqi_filename
        )
        add_trace_act_for_action(pipeline, expected_action, transition=transition)
        assert solve_output.variables["T"].startswith("object transition_")

    serializer, loqi_file = pipeline_to_loqi_files(
        tmp_path,
        pipeline,
        filename=loqi_filename,
    )[0]
    final_output = solve_reasoning(
        resolve_project_root() / "domain",
        loqi_file,
        tree=TREE_NAME,
    )

    assert final_output is not None
    assert final_output.result is True
    assert not final_output.exceptions
    assert "N" not in final_output.variables
    assert final_output.variables["P"].startswith("object ")


@pytest.mark.parametrize(
    ("language", "code", "expected_roles", "expected_actions", "loqi_filename"),
    SEQUENCE_CASES,
)
def test_solve_tree_sequences(
    tmp_path: Path,
    *,
    language: str,
    code: str,
    expected_roles: dict[int, list[str]],
    expected_actions: list[tuple[int, int]],
    loqi_filename: str,
):
    _pipeline, registry = _build_registry(code, language=language)
    _assert_line_roles(registry, expected_roles)
    _assert_solve_sequence(
        tmp_path,
        code=code,
        language=language,
        expected_actions=expected_actions,
        loqi_filename=loqi_filename,
    )


def _solve_next_step(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    expected_action: Action,
    *,
    loqi_filename: str,
) -> tuple[ReasoningResult, TransitionDeclaration]:
    serializer, loqi_file = pipeline_to_loqi_files(
        tmp_path,
        pipeline,
        filename=loqi_filename,
    )[0]
    solve_output = solve_reasoning(
        resolve_project_root() / "domain",
        loqi_file,
        tree=TREE_NAME,
    )

    assert solve_output is not None
    assert solve_output.result is True
    assert not solve_output.exceptions

    expected_action_name = serializer.object_name(expected_action)
    assert expected_action_name is not None
    assert solve_output.variables["N"] == f"object {expected_action_name}"

    transition_name = _object_name_from_variable(solve_output, "T")
    transition = serializer.object_by_name(transition_name)
    assert isinstance(transition, TransitionDeclaration)
    return solve_output, transition


def _object_name_from_variable(result: ReasoningResult, variable_name: str) -> str:
    value = result.variables.get(variable_name)
    assert value is not None
    prefix = "object "
    assert value.startswith(prefix)
    return value[len(prefix) :]
