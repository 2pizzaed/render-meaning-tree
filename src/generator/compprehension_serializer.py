"""Упаковка задачи генератора в SerializableQuestionTemplate банка вопросов CompPrehension.

Формат описан в ``src/resources/serializable_question_template.schema.json``. Факты
условия передаются RDF Turtle (``statementFactsTTL``): ситуацию условия выгружает
its_DomainModel (``domain-to-rdf``) вместе с базовым доменом модели. Определений
свойств, отношений и enum'ов writer не пишет, но иерархия классов, их метаданные и
объекты базового домена в TTL попадают.
"""

from __future__ import annotations

import copy
import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.ast_managers import CodeManager
from src.generator.concepts import CONCEPTS
from src.generator.helpers.ui_trace import resolve_button_action
from src.generator.problems import LearningProblem
from src.generator.question_html import QuestionHtml
from src.generator.registry import SituationRegistry
from src.generator.serialization import registry_to_loqi
from src.generator.skills import ERRORNEOUS_SKILLS, SKILLS
from src.helpers.bitflags import pack_flags
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import domain_to_rdf
from src.types import SupportedProgrammingLanguage

logger = logging.getLogger(__name__)

DOMAIN_SHORTNAME = "ctrl_flow_dt25"
QUESTION_VERSION = 3
QUESTION_TYPE = "ORDER"
QUESTION_DOMAIN_TYPE = "OrderActs"
ORDER_OPTIONS: dict[str, Any] = {
    "showTrace": True,
    "requireContext": True,
    "requireAllAnswers": True,
    "orderNumberOptions": {"position": "SUFFIX", "delimiter": "/"},
    "multipleSelectionEnabled": True,
    "showSupplementaryQuestions": False,
}
LANGUAGE_TAG_BITS: dict[SupportedProgrammingLanguage, int] = {
    "c++": 2,
    "java": 4,
    "python": 8,
}
QUESTION_NAME_EXCERPT_LENGTH = 48

# Символы, недопустимые в именах файлов, и всё, кроме букв, цифр, «-», «_», «.» и пробела.
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_NON_NAME_CHARS = re.compile(r"[^A-Za-z0-9\-._ ]+")


class QuestionTemplateError(Exception):
    """Задачу нельзя упаковать в вопрос; сообщение - причина для лога."""


def problem_to_question_template(
    problem: LearningProblem,
    statement: SituationRegistry,
    html: QuestionHtml,
    *,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """SerializableQuestionTemplate задачи.

    ``statement`` - ситуация условия (``problem_statement_registry``), ``html`` - HTML
    кода фрагмента (``render_question_html``).
    """
    serializer, loqi = registry_to_loqi(statement)
    tree_hash = _tree_hash(statement.code)
    language = statement.code.language
    name = question_name(problem.code, tree_hash, problem.variant_index)
    concepts = sorted(problem.concepts)
    concept_bits = pack_flags(CONCEPTS, concepts)

    metadata: dict[str, Any] = {
        "name": name,
        "domainShortname": DOMAIN_SHORTNAME,
        "templateId": str(tree_hash),
        "tagBits": LANGUAGE_TAG_BITS[language],
        "conceptBits": concept_bits,
        "lawBits": 0,
        "violationBits": 0,
        "traceConceptBits": concept_bits,
        "skillBits": pack_flags(SKILLS, sorted(problem.skills)),
        "solutionStructuralComplexity": len(problem.registry.trace_acts),
        "integralComplexity": problem.complexity,
        "solutionSteps": problem.student_steps,
        "distinctErrorsCount": len(problem.skills & ERRORNEOUS_SKILLS),
        "version": QUESTION_VERSION,
        "structureHash": str(tree_hash),
        "dateCreated": (created_at or datetime.now(UTC))
        .astimezone(UTC)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "language": language,
        "treeHashCode": tree_hash,
    }
    if problem.origin is not None:
        metadata["origin"] = problem.origin.origin
        metadata["originLicense"] = problem.origin.license

    return {
        "commonQuestion": {
            "questionData": {
                "questionType": QUESTION_TYPE,
                "questionText": html.text,
                "questionName": name,
                "questionDomainType": QUESTION_DOMAIN_TYPE,
                "options": copy.deepcopy(ORDER_OPTIONS),
                "answerObjects": _answer_objects(name, problem, statement, serializer, html),
                "statementFactsTTL": _statement_ttl(statement, loqi),
            },
            "concepts": concepts,
            "negativeLaws": [],
            "tags": [language],
        },
        "metadataList": [metadata],
    }


def question_name(code: str, tree_hash: int, variant_index: int) -> str:
    """Имя вопроса: начало кода, пригодное для имени файла, хэш дерева и номер варианта."""
    excerpt = re.sub(r"\s+", " ", code).strip()
    excerpt = _NON_NAME_CHARS.sub("_", _FORBIDDEN_NAME_CHARS.sub("", excerpt))
    excerpt = excerpt[:QUESTION_NAME_EXCERPT_LENGTH].rstrip(" .")
    return f"{excerpt}_{tree_hash}_{variant_index}"


def _answer_objects(
    name: str,
    problem: LearningProblem,
    statement: SituationRegistry,
    serializer: LoqiSerializer,
    html: QuestionHtml,
) -> list[dict[str, Any]]:
    """Ответы - кнопки HTML; domainInfo - LOQI-имя действия ситуации.

    Кнопку без действия или с неоднозначным действием пропускаем с предупреждением,
    но у каждого шага студента в корректной трассе (``student_step_indexes``) ответ
    должен быть.
    """
    answers: list[dict[str, Any]] = []
    for button in html.buttons:
        action_id = button.get("action_id")
        if action_id is None:
            continue
        try:
            action = resolve_button_action(statement, button)
        except LookupError as error:
            logger.warning("%s: кнопка %s пропущена: %s", name, button, error)
            continue
        action_name = serializer.object_name(action) if action is not None else None
        if action_name is None:
            logger.warning("%s: у кнопки %s нет действия, пропущена", name, button)
            continue
        answers.append(
            {
                "answerId": int(action_id),
                "hyperText": button["type"],
                "domainInfo": action_name,
                "concept": "action",
                "isRightCol": False,
            }
        )

    # Трасса задачи - в registry ветки, а имена объектов детерминированы структурой
    # ситуации, поэтому её serializer называет действия так же, как serializer условия.
    trace_serializer, _ = registry_to_loqi(problem.registry)
    answered = {answer["domainInfo"] for answer in answers}
    trace = problem.registry.trace_acts
    missing = sorted(
        {
            trace_serializer.object_name(trace[index].action) or repr(trace[index].action)
            for index in problem.student_step_indexes
        }
        - answered
    )
    if missing:
        raise QuestionTemplateError(f"нет кнопок для шагов корректной трассы: {', '.join(missing)}")
    return answers


def _statement_ttl(statement: SituationRegistry, loqi: str) -> str:
    config = statement.config
    if config is None:
        raise RuntimeError("SituationRegistry.config is not set")
    with tempfile.TemporaryDirectory(prefix="statement-", dir=config.temp_root) as directory:
        loqi_path = Path(directory) / "statement.loqi"
        loqi_path.write_text(loqi, encoding="utf-8")
        ttl = domain_to_rdf(config.model_dir, domain_loqi=loqi_path)
    if not isinstance(ttl, str) or not ttl.strip():
        raise QuestionTemplateError("its_DomainModel не выгрузил ситуацию в RDF (domain-to-rdf)")
    return ttl


def _tree_hash(code: CodeManager) -> int:
    tree_hash = code.ast.root.get("unique_hash")
    if not isinstance(tree_hash, int):
        raise QuestionTemplateError("у дерева MeaningTree нет unique_hash")
    return tree_hash
