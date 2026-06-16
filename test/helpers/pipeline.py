from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    PipelineRegistry,
    SituationDomainDataRegistry,
)
from src.generator.utilities import (
    code_file_to_pipeline,
    code_snippet_to_pipeline,
    pipeline_to_loqi,
)
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi
from test.helpers.env import write_text_file


def code_snippet_to_loqi_files(
    directory: Path,
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
    filename: str = "generated-domain.loqi",
) -> list[tuple[LoqiSerializer, Path]]:
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline_to_loqi_files(directory, pipeline, filename=filename)


def code_snippet_to_pipeline_registries(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> Sequence[PipelineRegistry]:
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline.flatten_results()


def pipeline_to_loqi_files(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    filename: str = "generated-domain.loqi",
) -> list[tuple[LoqiSerializer, Path]]:
    loqi_results = pipeline_to_loqi(pipeline)
    return [
        (
            serializer,
            write_text_file(
                directory, loqi, _loqi_filename(filename, index, len(loqi_results))
            ),
        )
        for index, (serializer, loqi) in enumerate(loqi_results, start=1)
    ]


def _loqi_filename(filename: str, index: int, total: int) -> str:
    if total == 1:
        return filename
    path = Path(filename)
    return f"{path.stem}-{index}{path.suffix}"


def validate_code_snippet_domain_loqi(
    directory: Path,
    code: str,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "procedural",
    tag: str | None = None,
    filename: str = "generated-domain.loqi",
) -> bool:
    loqi_files = code_snippet_to_loqi_files(
        directory,
        code,
        language=language,
        mode=mode,
        filename=filename,
    )
    return all(
        validate_domain_loqi(loqi_file, model_dir, tag=tag)
        for _serializer, loqi_file in loqi_files
    )


def validate_code_file_domain_loqi(
    directory: Path,
    code_file: str | Path,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "procedural",
    tag: str | None = None,
    filename: str = "generated-domain.loqi",
) -> bool:
    pipeline = code_file_to_pipeline(code_file, language=language, mode=mode)
    loqi_files = pipeline_to_loqi_files(directory, pipeline, filename=filename)
    return all(
        validate_domain_loqi(loqi_file, model_dir, tag=tag)
        for _serializer, loqi_file in loqi_files
    )
