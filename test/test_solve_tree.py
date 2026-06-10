import textwrap
from pathlib import Path

from src.generator.pipeline import DomainDataGeneratorPipeline
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
