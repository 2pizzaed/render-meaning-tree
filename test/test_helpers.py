import re

from src.generator.utilities import pipeline_to_loqi
from test.helpers import add_trace_act_for_line, code_snippet_to_pipeline, trace_acts_from_loqi


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
