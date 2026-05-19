import sys
import textwrap
from pathlib import Path

from src.generator.utilities import code_snippet_to_pipeline
from src.model.situation import TraceAct
from src.tpg_domain import solve_reasoning
from test.helpers import open_file_and_wait, pipeline_to_loqi_files, resolve_project_root


def test_plain_statements(tmp_path: Path):
    code, lang = textwrap.dedent("""
        x = 1
        y = 2
        a = x + y
    """), "python"

    pipeline = code_snippet_to_pipeline(
        code, language=lang
    )
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]

    entry_point = registry.get_construct_for(pipeline.code.ast.find_paths_by_type("program_entry_point")[0].id)
    assert entry_point

    x_assign_node = pipeline.code.line_number_to_ast_node(1)
    assert x_assign_node
    y_assign_node = pipeline.code.line_number_to_ast_node(2)
    assert y_assign_node

    registry.add(
        trace_act := TraceAct(
            registry.get_actions_for(
                x_assign_node.id,
            )[0],
            entry_point.rule.compiled_transitions_from_role("first")[0],
            pipeline,
        )
    )
    registry.variables["P"] = trace_act
    serializer, loqi_file = pipeline_to_loqi_files(
        tmp_path, pipeline,
        filename="plain_statements.loqi",
    )[0]
    assert serializer.object_name(registry.trace_acts[0]) is not None
    solve_output = solve_reasoning(
        resolve_project_root() / 'domain',
        loqi_file,
        tree="findCorrect",
        reasoner_output_stream=sys.stdout
    )
    assert solve_output and solve_output.result
    print(solve_output)
    assert not len(solve_output.exceptions)
