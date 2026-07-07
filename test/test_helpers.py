import re
from pathlib import Path

import test.helpers.dot as helpers_dot_module
import test.helpers.pipeline as helpers_pipeline_module
from src.generator.helpers import add_trace_act_for_line
from src.generator.utilities import code_snippet_to_pipeline, pipeline_to_loqi
from src.helpers.tpg import (
    restore_trace_from_loqi,
    trace_acts_from_loqi,
    trace_state_from_loqi,
)
from src.model.rules import InterruptionType
from test.helpers import (
    render_trace_acts_artifacts,
    resolve_test_output_dir,
    trace_acts_to_dot,
)


def test_trace_acts_from_loqi_restores_trace_chain() -> None:
    code = """
    x = 1
    y = 2
    """
    source_pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(source_pipeline, 1)
    add_trace_act_for_line(source_pipeline, 2)
    _serializer, loqi_text = pipeline_to_loqi(source_pipeline)[0]

    target_pipeline = code_snippet_to_pipeline(code, language="python")
    trace_acts = trace_acts_from_loqi(loqi_text, target_pipeline)

    expected = [
        (
            trace_act.action.ast_id,
            trace_act.action.rule.role,
            trace_act.used_transition.from_role if trace_act.used_transition else None,
            trace_act.used_transition.to_role if trace_act.used_transition else None,
        )
        for trace_act in source_pipeline.registry.trace_acts
    ]
    actual = [
        (
            trace_act.action.ast_id,
            trace_act.action.rule.role,
            trace_act.used_transition.from_role if trace_act.used_transition else None,
            trace_act.used_transition.to_role if trace_act.used_transition else None,
        )
        for trace_act in trace_acts
    ]

    assert actual == expected
    assert target_pipeline.registry.trace_acts == trace_acts


def test_trace_acts_from_loqi_orders_chain_by_directly_before_of() -> None:
    code = """
    x = 1
    y = 2
    """
    source_pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(source_pipeline, 1)
    add_trace_act_for_line(source_pipeline, 2)
    _serializer, loqi_text = pipeline_to_loqi(source_pipeline)[0]

    trace_act_blocks = re.findall(
        r"(?:var\s+\w+\s*=\s*)?obj\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*TraceAct\s*\{.*?\}\n?",
        loqi_text,
        re.DOTALL,
    )
    reordered_loqi = loqi_text
    for trace_act_block in trace_act_blocks:
        reordered_loqi = reordered_loqi.replace(trace_act_block, "", 1)
    reordered_loqi += "\n" + "\n".join(reversed(trace_act_blocks))

    target_pipeline = code_snippet_to_pipeline(code, language="python")
    trace_acts = trace_acts_from_loqi(reordered_loqi, target_pipeline)

    assert [trace_act.action.rule.role for trace_act in trace_acts] == [
        trace_act.action.rule.role for trace_act in source_pipeline.registry.trace_acts
    ]


def test_trace_state_from_loqi_replaces_registry_state() -> None:
    code = """
    x = 1
    """
    pipeline = code_snippet_to_pipeline(code, language="python")
    loqi_text = """
    var S = obj trace_state_break : TraceState {
        interruption_mode = InterruptionType:break;
    }
    """

    trace_state = trace_state_from_loqi(loqi_text, pipeline)

    assert trace_state is not None
    assert trace_state.interruption_mode.value == "break"
    assert pipeline.registry.trace_state is trace_state
    assert pipeline.registry.variables["S"] is trace_state


def test_restore_trace_from_loqi_restores_state_and_trace_chain() -> None:
    code = """
    x = 1
    y = 2
    """
    source_pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(source_pipeline, 1)
    add_trace_act_for_line(source_pipeline, 2)
    _serializer, loqi_text = pipeline_to_loqi(source_pipeline)[0]

    target_pipeline = code_snippet_to_pipeline(code, language="python")
    trace_acts, trace_state = restore_trace_from_loqi(loqi_text, target_pipeline)

    assert trace_state is target_pipeline.registry.trace_state
    assert trace_state is target_pipeline.registry.variables["S"]
    assert trace_acts == target_pipeline.registry.trace_acts


def test_trace_acts_to_dot_groups_actions_by_construct_and_renders_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    code = """
x = 1
y = 2
"""
    pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(pipeline, 1)
    add_trace_act_for_line(pipeline, 2)

    def fake_render_dot_png(dot_text: str, path: Path) -> Path:
        path.write_bytes(dot_text.encode("utf-8"))
        return path

    monkeypatch.setattr(helpers_dot_module, "render_dot_png", fake_render_dot_png)
    monkeypatch.setenv("PNG_DOT_OUTPUT", "1")

    trace_acts = pipeline.registry.trace_acts
    dot = trace_acts_to_dot(trace_acts)
    output_dir = resolve_test_output_dir(tmp_path)
    dot_path, png_path = render_trace_acts_artifacts(
        output_dir,
        trace_acts,
        filename_stem="trace-act-graph",
    )

    assert "subgraph cluster_" in dot
    assert "global_statements_structure" in dot
    assert "x: int = 1" in dot
    assert "role:" in dot
    assert dot_path.exists()
    assert png_path.exists()


def test_trace_acts_to_dot_marks_transparency_without_replacing_role_or_stop_color() -> (
    None
):
    pipeline = code_snippet_to_pipeline("x = 1", language="python")
    trace_acts = pipeline.registry.trace_acts

    dot = trace_acts_to_dot(trace_acts, solver_stops={0})

    assert 'fillcolor="#e0f2fe"' in dot
    assert 'color="#b45309"' in dot
    assert "penwidth=3.0" in dot
    assert 'style="rounded,filled,diagonals,bold"' in dot


def test_trace_acts_to_dot_skips_png_when_png_dot_output_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    code = """
x = 1
"""
    pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(pipeline, 1)

    monkeypatch.setenv("PNG_DOT_OUTPUT", "0")

    def fail_render_dot_png(_dot_text: str, _path: Path) -> Path:
        raise AssertionError("render_dot_png should not be called when PNG is disabled")

    monkeypatch.setattr(helpers_dot_module, "render_dot_png", fail_render_dot_png)

    trace_acts = pipeline.registry.trace_acts
    output_dir = resolve_test_output_dir(tmp_path)
    dot_path, png_path = render_trace_acts_artifacts(
        output_dir,
        trace_acts,
        filename_stem="trace-act-graph",
    )

    assert dot_path.exists()
    assert not png_path.exists()


def test_pipeline_debug_json_artifacts_skips_png_when_png_dot_output_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    code = """
x = 1
"""
    pipeline = code_snippet_to_pipeline(code, language="python")
    monkeypatch.setenv("PNG_DOT_OUTPUT", "false")

    def fail_render_dot_png(_dot_text: str, _path: Path) -> Path:
        raise AssertionError("render_dot_png should not be called when PNG is disabled")

    monkeypatch.setattr(helpers_pipeline_module, "render_dot_png", fail_render_dot_png)

    artifacts = helpers_pipeline_module.pipeline_debug_json_artifacts(
        tmp_path,
        pipeline,
        filename_stem="pipeline",
    )

    assert "meaning_tree_dot" in artifacts
    assert "meaning_tree_png" not in artifacts


def test_trace_acts_to_dot_labels_edges_for_non_none_interruption_mode() -> None:
    code = """
    x = 1
    y = 2
    """
    pipeline = code_snippet_to_pipeline(code, language="python")
    add_trace_act_for_line(pipeline, 1)
    add_trace_act_for_line(pipeline, 2)
    trace_acts = pipeline.registry.trace_acts
    dot = trace_acts_to_dot(
        trace_acts,
        trace_act_interruptions=[(0, InterruptionType.BREAK)],
    )
    assert "break" in dot
