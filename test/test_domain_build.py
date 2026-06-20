from __future__ import annotations

from pathlib import Path

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import code_snippet_to_pipeline
from src.tpg_domain import validate_domain_loqi
from test.helpers import (
    code_snippet_to_loqi_files,
    resolve_test_output_dir,
    validate_code_snippet_domain_loqi,
)


def _single_construct(pipeline: DomainDataGeneratorPipeline, rule_name: str):
    matches = [
        construct
        for construct in pipeline.registry.constructs.values()
        if construct.rule.name == rule_name
    ]
    assert len(matches) == 1
    return matches[0]


def test_domain_build_validates_elif_chain_and_links_each_condition_to_its_branch(tmp_path: Path) -> None:
    output_dir = resolve_test_output_dir(tmp_path)
    code = """
def main(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    else:
        return 4
"""

    assert validate_code_snippet_domain_loqi(output_dir, code, filename="elif-chain.loqi")

    pipeline = code_snippet_to_pipeline(code)
    if_construct = _single_construct(pipeline, "if_structure")
    roles = [action.rule.role for action in pipeline.get_related_actions(if_construct)]

    assert roles.count("first_cond") == 1
    assert roles.count("next_cond") == 2
    assert roles.count("if_branch") == 3
    assert roles.count("else_branch") == 1


def test_domain_build_validates_elif_conditions_with_single_true_value(tmp_path: Path) -> None:
    output_dir = resolve_test_output_dir(tmp_path)
    code = """
def main(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 3
"""

    assert validate_code_snippet_domain_loqi(output_dir, code, filename="elif-condition-values.loqi")

    pipeline = code_snippet_to_pipeline(code)
    if_construct = _single_construct(pipeline, "if_structure")
    condition_actions = [
        action
        for action in pipeline.get_related_actions(if_construct)
        if action.rule.role in {"first_cond", "next_cond"}
    ]

    assert condition_actions
    assert all(action.values == [True] for action in condition_actions)


def test_domain_build_validates_sequence_action_chain_in_execution_order(tmp_path: Path) -> None:
    output_dir = resolve_test_output_dir(tmp_path)
    code = """
def main():
    x = 1
    y = 2
    return x + y
"""

    assert validate_code_snippet_domain_loqi(output_dir, code, filename="sequence-order.loqi")

    pipeline = code_snippet_to_pipeline(code)
    block_constructs = [
        construct
        for construct in pipeline.registry.constructs.values()
        if construct.rule.name == "block_structure"
    ]
    function_block = max(block_constructs, key=lambda construct: len(pipeline.get_related_actions(construct)))

    assert [action.rule.role for action in pipeline.get_related_actions(function_block)] == [
        "BEGIN",
        "first",
        "next",
        "next",
        "END",
    ]


def test_domain_build_validates_while_condition_values(tmp_path: Path) -> None:
    output_dir = resolve_test_output_dir(tmp_path)
    code = """
def main(x):
    while x > 0:
        x = x - 1
    return x
"""

    assert validate_code_snippet_domain_loqi(output_dir, code, filename="while-condition-values.loqi")

    pipeline = code_snippet_to_pipeline(code)
    while_construct = _single_construct(pipeline, "while_structure")
    condition_actions = [
        action
        for action in pipeline.get_related_actions(while_construct)
        if action.rule.role == "cond"
    ]

    assert len(condition_actions) == 1
    assert condition_actions[0].values == [True, True, False]


def test_domain_build_validates_simple_branch_domain(tmp_path: Path) -> None:
    output_dir = resolve_test_output_dir(tmp_path)
    code = """
def main():
    x = 1
    y = 2
    if x > 0:
        return True
    return False
"""

    loqi_files = code_snippet_to_loqi_files(output_dir, code, filename="simple-branch.loqi")

    assert all(validate_domain_loqi(loqi_file, "domain") for _serializer, loqi_file in loqi_files)
