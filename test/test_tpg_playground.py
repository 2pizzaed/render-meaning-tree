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
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.process()
    return pipeline_results_to_loqi(pipeline)


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
    loqi = ""
    for registry in pipeline.flatten_results():
        for item in registry.collect():
            loqi += serializer.serialize(item) + "\n\n"
    return loqi


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


@pytest.mark.skipif(
    os.getenv("TPG_PLAYGROUND_RUN") != "1",
    reason="Set TPG_PLAYGROUND_RUN=1 to run the local TPG playground.",
)
def test_tpg_pipeline_playground(tmp_path: Path) -> None:
    code = """
def main():
    x = 1
    if x > 0:
        return True
    return False
"""

    loqi_file = code_snippet_to_loqi_file(tmp_path, code)

    assert validate_domain_loqi(loqi_file, "domain")
