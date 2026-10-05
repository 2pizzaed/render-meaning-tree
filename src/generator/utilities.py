from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from src.ast_managers import CodeManager, prepare_code
from src.generator.pipeline import DomainDataGeneratorPipeline, SituationRegistry
from src.localization import load_bundle
from src.model.rules import ConstructDeclaration
from src.serialization.adapters.rules import build_rules_loqi_adapters
from src.serialization.adapters.situation import build_situation_loqi_adapters
from src.serialization.localized_names import localized_names_decorator
from src.serialization.loqi import LoqiDecorator, LoqiSerializer

DEFINITIONS_BUNDLE = "definitions"


def code_snippet_to_pipeline(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> DomainDataGeneratorPipeline:
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    return DomainDataGeneratorPipeline.from_code(manager).run()


def code_snippet_to_registry(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> SituationRegistry:
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    return code_manager_to_registry(manager)


def code_manager_to_registry(manager: CodeManager) -> SituationRegistry:
    """Сгенерировать ситуацию, когда генерация даёт ровно один результат."""
    [registry] = DomainDataGeneratorPipeline.from_code(manager).run().results()
    return registry


def code_file_to_pipeline(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> DomainDataGeneratorPipeline:
    code = Path(code_file).read_text(encoding="utf-8")
    return code_snippet_to_pipeline(code, language=language, mode=mode)


def default_loqi_decorators(
    code: CodeManager | None = None,
    rules: Sequence[ConstructDeclaration] = (),
) -> tuple[LoqiDecorator, ...]:
    return (localized_names_decorator(load_bundle(DEFINITIONS_BUNDLE), code, rules),)


def serialize_domain_objects(
    objects: list[Any],
    *,
    variables: dict[str, Any] | None = None,
    decorators: Iterable[LoqiDecorator] | None = None,
) -> LoqiSerializer:
    adapters = {
        **build_rules_loqi_adapters(),
        **build_situation_loqi_adapters(),
    }
    serializer = LoqiSerializer(
        adapters_by_type=adapters,
        decorators=default_loqi_decorators() if decorators is None else decorators,
    )
    serializer.serialize_many(objects, variables=variables)
    return serializer


def serialize_domain_objects_to_loqi(
    objects: list[Any],
    *,
    variables: dict[str, Any] | None = None,
    decorators: Iterable[LoqiDecorator] | None = None,
) -> tuple[LoqiSerializer, str]:
    serializer = serialize_domain_objects(objects, variables=variables, decorators=decorators)
    return serializer, serializer.render()


def registry_to_loqi(
    registry: SituationRegistry,
    *,
    variables: dict[str, Any] | None = None,
) -> tuple[LoqiSerializer, str]:
    # В unit-тестах code бывает заглушкой: локализованные имена без кода не строятся.
    code = registry.code if isinstance(registry.code, CodeManager) else None
    return serialize_domain_objects_to_loqi(
        registry.domain_objects(),
        variables={**registry.variables, **(variables or {})},
        decorators=default_loqi_decorators(code, registry.rules),
    )


def pipeline_to_loqi(
    pipeline: DomainDataGeneratorPipeline,
    *,
    variables: dict[str, Any] | None = None,
) -> list[tuple[LoqiSerializer, str]]:
    return [
        registry_to_loqi(registry, variables=variables)
        for registry in pipeline.results()
    ]
