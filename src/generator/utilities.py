from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ast_managers import prepare_code
from src.generator.pipeline import DomainDataGeneratorPipeline, PipelineRegistry
from src.serialization.adapters.rules import build_rules_loqi_adapters
from src.serialization.adapters.situation import build_situation_loqi_adapters
from src.serialization.loqi import LoqiSerializer


def code_snippet_to_pipeline(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
) -> DomainDataGeneratorPipeline:
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = DomainDataGeneratorPipeline(manager)
    pipeline.process()
    return pipeline


def code_file_to_pipeline(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "simple",
) -> DomainDataGeneratorPipeline:
    code = Path(code_file).read_text(encoding="utf-8")
    return code_snippet_to_pipeline(code, language=language, mode=mode)


def collect_registry_objects(
    registry: PipelineRegistry,
) -> list[Any]:
    return registry.collect()


def serialize_domain_objects(
    objects: list[Any],
    *,
    variables: dict[str, Any] | None = None,
) -> LoqiSerializer:
    adapters = {
        **build_rules_loqi_adapters(),
        **build_situation_loqi_adapters(),
    }
    serializer = LoqiSerializer(adapters_by_type=adapters)
    serializer.serialize_many(objects, variables=variables)
    return serializer


def _registry_variables(
    registry: PipelineRegistry,
    variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    registry_variables = getattr(registry, "variables", None)
    if not registry_variables:
        return variables
    if variables is None:
        return dict(registry_variables)
    return {**registry_variables, **variables}


def serialize_domain_objects_to_loqi(
    objects: list[Any],
    *,
    variables: dict[str, Any] | None = None,
) -> tuple[LoqiSerializer, str]:
    serializer = serialize_domain_objects(objects, variables=variables)
    return serializer, serializer.render()


def registry_to_loqi(
    registry: PipelineRegistry,
    *,
    variables: dict[str, Any] | None = None,
) -> tuple[LoqiSerializer, str]:
    return serialize_domain_objects_to_loqi(
        collect_registry_objects(registry),
        variables=_registry_variables(registry, variables),
    )


def pipeline_to_loqi(
    pipeline: DomainDataGeneratorPipeline,
    *,
    variables: dict[str, Any] | None = None,
) -> list[tuple[LoqiSerializer, str]]:
    return [
        registry_to_loqi(registry, variables=variables)
        for registry in pipeline.flatten_results()
    ]
