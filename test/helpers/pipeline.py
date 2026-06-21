from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

from src.dot import render_dot_png
from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    PipelineRegistry,
)
from src.generator.utilities import (
    code_file_to_pipeline,
    code_snippet_to_pipeline,
    pipeline_to_loqi,
)
from src.meaning_tree import to_dot
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi
from src.types import JSON
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


def pipeline_debug_json_artifacts(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    filename_stem: str = "pipeline",
) -> dict[str, Path]:
    """Сохранить SourceMap, токены, Meaning Tree и Meaning Tree DOT в артефакты."""
    artifacts = {
        "source_map": pipeline.code.source_map,
        "tokens": {
            "type": "TokenList",
            "items": _pipeline_tokens_to_json(pipeline),
        },
        "meaning_tree": pipeline.code.ast.root,
    }
    paths = {
        name: _write_json_file(directory, content, f"{filename_stem}-{suffix}.json")
        for name, suffix, content in (
            ("source_map", "source-map", artifacts["source_map"]),
            ("tokens", "tokens", artifacts["tokens"]),
            ("meaning_tree", "meaning-tree", artifacts["meaning_tree"]),
        )
    }
    meaning_tree_dot = to_dot(
        "json",
        json.dumps(artifacts["meaning_tree"], ensure_ascii=False),
    )
    if meaning_tree_dot is not None:
        dot_path = write_text_file(
            directory,
            meaning_tree_dot,
            f"{filename_stem}-meaning-tree.dot",
        )
        paths["meaning_tree_dot"] = dot_path
        paths["meaning_tree_png"] = render_dot_png(
            meaning_tree_dot,
            directory / f"{filename_stem}-meaning-tree.png",
        )
    return paths


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


def _write_json_file(directory: Path, content: Any, filename: str) -> Path:
    return write_text_file(
        directory,
        json.dumps(_json_safe(content), ensure_ascii=False, indent=2),
        filename,
    )


def _pipeline_tokens_to_json(pipeline: DomainDataGeneratorPipeline) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for index in range(pipeline.code.token_count):
        token = pipeline.code.get_token(index)
        if token is not None:
            tokens.append(_token_to_json(token))
    return tokens


def _token_to_json(token: Any) -> dict[str, Any]:
    return {
        "id": getattr(token, "_id", None),
        "value": getattr(token, "value", ""),
        "type": getattr(token, "type", ""),
        "class_name": getattr(token, "class_name", ""),
        "index": getattr(token, "index", None),
        "css_classes": list(getattr(token, "css_classes", [])),
        "ast_node": _node_path_to_json(getattr(token, "ast_node", None)),
    }


def _node_path_to_json(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    path: list[dict[str, Any]] = []
    current = node
    while current is not None:
        path.append(
            {
                "id": getattr(current, "id", None),
                "type": getattr(current, "type", ""),
                "field_name": getattr(current, "field_name", None),
                "field_type": getattr(current, "field_type", None),
                "container_field_id": getattr(current, "container_field_id", None),
            }
        )
        current = getattr(current, "parent", None)
    return {
        "id": getattr(node, "id", None),
        "type": getattr(node, "type", ""),
        "path": list(reversed(path)),
    }


def _json_safe(value: Any) -> JSON | list[Any] | str | int | float | bool | None:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return repr(value)
