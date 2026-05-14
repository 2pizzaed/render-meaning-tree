from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.ast_managers import prepare_code
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.serialization.adapters.rules import build_rules_loqi_adapters
from src.serialization.adapters.situation import build_situation_loqi_adapters
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi


def write_temp_text_file(
    tmp_path: Path,
    content: str,
    filename: str = "input.loqi",
) -> Path:
    """Create a temporary text file and return its ready-to-use path."""
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def code_snippet_to_loqi(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
) -> str:
    """Run a code snippet through DomainDataGeneratorPipeline and return LOQI."""
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline_results_to_loqi(pipeline)


def code_snippet_to_pipeline(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
) -> DomainDataGeneratorPipeline:
    """Run a code snippet through DomainDataGeneratorPipeline and return it."""
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.process()
    return pipeline


def code_file_to_loqi(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "simple",
) -> str:
    """Run source code from a file through the pipeline and return LOQI."""
    code = Path(code_file).read_text(encoding="utf-8")
    return code_snippet_to_loqi(code, language=language, mode=mode)


def code_snippet_to_loqi_file(
    tmp_path: Path,
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
    filename: str = "generated-domain.loqi",
) -> Path:
    loqi = code_snippet_to_loqi(code, language=language, mode=mode)
    return write_temp_text_file(tmp_path, loqi, filename)


def pipeline_results_to_loqi(pipeline: DomainDataGeneratorPipeline) -> str:
    adapters = {
        **build_rules_loqi_adapters(),
        **build_situation_loqi_adapters(),
    }
    serializer = LoqiSerializer(adapters_by_type=adapters)
    roots = []
    for registry in pipeline.flatten_results():
        for item in registry.collect():
            roots.append(item)
    return serializer.serialize_many(roots)


def validate_code_snippet_domain_loqi(
    tmp_path: Path,
    code: str,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "simple",
    tag: str | None = None,
) -> bool:
    loqi = code_snippet_to_loqi(code, language=language, mode=mode)
    loqi_file = write_temp_text_file(tmp_path, loqi, "generated-domain.loqi")
    return validate_domain_loqi(loqi_file, model_dir, tag=tag)


def validate_code_file_domain_loqi(
    tmp_path: Path,
    code_file: str | Path,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "simple",
    tag: str | None = None,
) -> bool:
    loqi = code_file_to_loqi(code_file, language=language, mode=mode)
    loqi_file = write_temp_text_file(tmp_path, loqi, "generated-domain.loqi")
    return validate_domain_loqi(loqi_file, model_dir, tag=tag)


def _single_construct(pipeline: DomainDataGeneratorPipeline, rule_name: str):
    matches = [
        construct
        for construct in pipeline.registry.constructs.values()
        if construct.rule.name == rule_name
    ]
    assert len(matches) == 1
    return matches[0]


def test_tpg_pipeline_elif_chain_links_each_condition_to_its_branch() -> None:
    pipeline = code_snippet_to_pipeline(
        """
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
    )
    if_construct = _single_construct(pipeline, "if_structure")
    roles = [action.rule.role for action in pipeline.get_related_actions(if_construct)]

    assert roles.count("first_cond") == 1
    assert roles.count("next_cond") == 2
    assert roles.count("if_branch") == 3
    assert roles.count("else_branch") == 1


def test_tpg_pipeline_elif_conditions_do_not_get_loop_iteration_values() -> None:
    pipeline = code_snippet_to_pipeline(
        """
def main(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 3
"""
    )
    if_construct = _single_construct(pipeline, "if_structure")
    condition_actions = [
        action
        for action in pipeline.get_related_actions(if_construct)
        if action.rule.role in {"first_cond", "next_cond"}
    ]

    assert condition_actions
    assert all(action.values == [] for action in condition_actions)


def test_tpg_pipeline_sequence_action_chain_follows_execution_order() -> None:
    pipeline = code_snippet_to_pipeline(
        """
def main():
    x = 1
    y = 2
    return x + y
"""
    )
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


def test_tpg_pipeline_while_condition_gets_multiple_condition_values() -> None:
    pipeline = code_snippet_to_pipeline(
        """
def main(x):
    while x > 0:
        x = x - 1
    return x
"""
    )
    while_construct = _single_construct(pipeline, "while_structure")
    condition_actions = [
        action
        for action in pipeline.get_related_actions(while_construct)
        if action.rule.role == "cond"
    ]

    assert len(condition_actions) == 1
    assert condition_actions[0].values == [True, False]


@pytest.mark.skipif(
    os.getenv("TPG_PLAYGROUND_RUN") != "1",
    reason="Set TPG_PLAYGROUND_RUN=1 to run the local TPG playground.",
)
def test_tpg_pipeline_playground(tmp_path: Path) -> None:
    code = """
def main():
    x = 1
    y = 2
    if x > 0:
        return True
    return False
"""

    loqi_file = code_snippet_to_loqi_file(tmp_path, code)
    os.startfile(loqi_file)

    '''
    TODO: Экспортировать в loqi нужно сначала rules сущности, потом situation
    Нужно проходиться не по construct decl actions, а по автомату, чтобы понимать где действие first, а где куча next, сейчас всё уходит в first или вообще не связывается дальше первого statement
    '''

    assert validate_domain_loqi(loqi_file, "domain")
