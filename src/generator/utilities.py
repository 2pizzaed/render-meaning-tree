from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.ast_managers import CodeManager, prepare_code
from src.generator.compprehension_serializer import (
    QuestionTemplateError,
    problem_to_question_template,
)
from src.generator.pipeline import LearningProblemGeneratorPipeline
from src.generator.problems import (
    DEFAULT_SEED,
    LearningProblem,
    ProblemGenerationConfig,
)
from src.generator.question_html import render_question_html
from src.generator.registry import SituationRegistry
from src.generator.value_plan import action_key
from src.model.situation import SemanticValue

logger = logging.getLogger(__name__)


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


def problem_statement_registry(
    base: SituationRegistry, problem: LearningProblem
) -> SituationRegistry:
    """Ситуация условия задачи: до первого шага студента, с цепочками значений задачи.

    ``base`` - исходная ситуация фрагмента: registry генератора, который после
    ветвления хранит корневой акт и значения по умолчанию. Сам ``base`` не меняется.
    """
    statement = base.clone()
    for action in statement.all_actions():
        values = problem.values.get(action_key(action))
        if values is not None:
            action.values = [SemanticValue(value) for value in values]
            action.bind_values()
    return statement


def code_snippet_to_question_templates(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
    seed: int = DEFAULT_SEED,
    config: ProblemGenerationConfig | None = None,
    origin: str | None = None,
    origin_license: str | None = None,
) -> list[dict[str, Any]]:
    """Задачи по фрагменту в формате SerializableQuestionTemplate банка CompPrehension.

    Задача, которую нельзя упаковать (нет кнопок для действий трассы, сбой выгрузки
    RDF), пропускается с предупреждением в логе.
    """
    manager = prepare_code(code, language, mode=mode)  # type: ignore[arg-type]
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, seed=seed, config=config)
    if origin is not None:
        pipeline.set_origin(origin, origin_license)
    problems = pipeline.run().results()
    if not problems:
        return []

    html = render_question_html(manager)
    created_at = datetime.now(UTC)
    templates: list[dict[str, Any]] = []
    for problem in problems:
        statement = problem_statement_registry(pipeline.registry, problem)
        try:
            templates.append(
                problem_to_question_template(problem, statement, html, created_at=created_at)
            )
        except QuestionTemplateError as error:
            logger.warning(
                "%s, вариант #%d: задача не упакована: %s",
                pipeline.describe(),
                problem.variant_index,
                error,
            )
    return templates
