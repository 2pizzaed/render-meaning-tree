from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ast_managers import prepare_code
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.serialization.adapters.rules import build_rules_loqi_adapters
from src.serialization.adapters.situation import build_situation_loqi_adapters
from src.serialization.loqi import LoqiSerializer


def code_snippet_to_pipeline(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
) -> DomainDataGeneratorPipeline:
    """Построить situation domain pipeline для фрагмента кода."""
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.process()
    return pipeline


def code_snippet_to_loqi(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
) -> str:
    """Построить pipeline для фрагмента кода и экспортировать результат в LOQI."""
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline_results_to_loqi(pipeline)


def code_file_to_pipeline(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "simple",
) -> DomainDataGeneratorPipeline:
    """Построить pipeline для исходного файла."""
    code = Path(code_file).read_text(encoding="utf-8")
    return code_snippet_to_pipeline(code, language=language, mode=mode)


def code_file_to_loqi(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "simple",
) -> str:
    """Построить pipeline для исходного файла и экспортировать результат в LOQI."""
    pipeline = code_file_to_pipeline(code_file, language=language, mode=mode)
    return pipeline_results_to_loqi(pipeline)


def pipeline_results_to_loqi(pipeline: DomainDataGeneratorPipeline) -> str:
    """Экспортировать собранные registry pipeline в LOQI."""
    adapters = {
        **build_rules_loqi_adapters(),
        **build_situation_loqi_adapters(),
    }
    serializer = LoqiSerializer(adapters_by_type=adapters)
    roots: list[Any] = []
    for registry in pipeline.flatten_results():
        roots.extend(registry.collect())
    return serializer.serialize_many(roots)
