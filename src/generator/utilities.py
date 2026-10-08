from __future__ import annotations

from pathlib import Path

from src.ast_managers import CodeManager, prepare_code
from src.generator.pipeline import LearningProblemGeneratorPipeline
from src.generator.problems import (
    DEFAULT_SEED,
    LearningProblem,
    ProblemGenerationConfig,
)
from src.generator.registry import SituationRegistry


def code_snippet_to_registry(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> SituationRegistry:
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    return code_manager_to_registry(manager)


def code_file_to_registry(
    code_file: str | Path,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> SituationRegistry:
    code = Path(code_file).read_text(encoding="utf-8")
    return code_snippet_to_registry(code, language=language, mode=mode)


def code_manager_to_registry(manager: CodeManager) -> SituationRegistry:
    """Одна ситуация со значениями условий по умолчанию, без рассуждателя."""
    pipeline = LearningProblemGeneratorPipeline.from_code(manager)
    pipeline.run_until("assign_default_values")
    if pipeline.is_terminated:
        raise ValueError(f"Situation generation stopped: {pipeline.termination_reason}")
    return pipeline.registry


def code_snippet_to_problems(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
    seed: int = DEFAULT_SEED,
    config: ProblemGenerationConfig | None = None,
) -> list[LearningProblem]:
    """Учебные задачи по фрагменту: до ``config.top_k`` вариантов значений условий."""
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, seed=seed, config=config)
    return pipeline.run().results()
