"""Verify feature selection against real MeaningTree/findCorrect output."""

from pathlib import Path

import pytest

from src.generator.concepts import collect_concepts
from src.generator.skills import collect_skills, is_everything_evaluated
from src.generator.utilities import code_snippet_to_registry
from src.helpers.tpg.reasoning import solve_graph_full_reasoning
from src.model.situation import SemanticValue
from test.helpers.env import resolve_project_root


@pytest.mark.parametrize(
    ("code", "values", "expected", "excluded"),
    [
        (
            "i = 0\nwhile i < 2:\n    if i == 0:\n        i = i + 1\n    else:\n        i = i * 2\ndef unused():\n    return 'hidden'\n",
            {"if_structure": [True, False]},
            {"assignment", "arithmetic", "while_loop", "loop_iteration", "if", "else"},
            {"function", "return", "strings", "recursion", "call_depth"},
        ),
        (
            "def f():\n    return 1\nx = f()\ny = f()\n",
            {},
            {"function", "return", "program_function_call", "var_declaration"},
            {"recursion", "call_depth"},
        ),
        (
            "def f(n):\n    if n > 0:\n        return f(n - 1)\n    return n\nx = f(1)\n",
            {"if_structure": [True, False]},
            {
                "function",
                "return",
                "program_function_call",
                "recursion",
                "call_depth",
                "arithmetic",
            },
            set(),
        ),
    ],
    ids=["loop_branches", "sequential_calls", "recursive_call"],
)
def test_features_on_correct_traces(
    tmp_path: Path,
    code: str,
    values: dict[str, list[bool]],
    expected: set[str],
    excluded: set[str],
) -> None:
    registry = code_snippet_to_registry(code)
    registry.variables["P"] = registry.trace_acts[0]
    for action in registry.all_actions():
        if (
            "condition" in action.rule.kind_classes
            and action.parent.rule.name in values
        ):
            action.values = [
                SemanticValue(value) for value in values[action.parent.rule.name]
            ]
            action.bind_values()
    solve_graph_full_reasoning(
        tmp_path,
        registry,
        model_dir=resolve_project_root() / "domain",
    )
    concepts = collect_concepts(registry.code.ast, registry.trace_acts)
    skills = collect_skills(registry.code.ast, registry.trace_acts)
    assert expected <= concepts
    assert not excluded & concepts
    assert is_everything_evaluated(registry.code.ast, registry.trace_acts)
    assert "passed_action_repeat" in skills
    if "while_loop" in expected:
        assert "condition_value_selects_next" in skills
        assert "alternative_single_branch" in skills
    if "function" in expected:
        assert {
            "function_body_runs_on_call",
            "function_not_resumed_after_exit",
            "interruption_exits_constructs",
        } <= skills
