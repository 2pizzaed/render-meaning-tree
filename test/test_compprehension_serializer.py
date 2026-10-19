import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from src.ast_managers import prepare_code
from src.generator.compprehension_serializer import (
    DOMAIN_SHORTNAME,
    QUESTION_VERSION,
    problem_to_question_template,
    question_name,
)
from src.generator.pipeline import LearningProblemGeneratorPipeline
from src.generator.pipeline.classification import integral_complexity
from src.generator.problems import LearningProblem, ProblemGenerationConfig
from src.generator.question_html import render_question_html
from src.generator.registry import SituationRegistry
from src.generator.utilities import (
    code_snippet_to_question_templates,
    problem_statement_registry,
)
from src.generator.value_plan import ActionKey, action_key
from src.model.situation import SemanticValue

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "resources"
    / "serializable_question_template.schema.json"
)
FAST_CONFIG = ProblemGenerationConfig(random_variants=0, max_loop_iterations=2)
BRANCH_CODE = textwrap.dedent(
    """
    x = 3
    if x > 2:
        x = 1
    else:
        x = 2
    print(x)
    """
)


def test_question_name_keeps_file_safe_code_excerpt_hash_and_variant():
    name = question_name('if a > "b":\n    print(a)\n', 42, 3)

    # Запрещённые в именах файлов символы удаляются, прочие - заменяются на «_».
    assert name == "if a  b print_a__42_3"


def test_question_name_cuts_code_excerpt():
    name = question_name("x = 1\n" * 20, -7, 0)

    assert name.endswith("_-7_0")
    assert len(name.removesuffix("_-7_0")) <= 48


def test_integral_complexity_grows_with_steps_and_stays_in_unit_interval():
    simple = integral_complexity(student_steps=2, cyclomatic_complexity=1, concept_count=1)
    complex_ = integral_complexity(student_steps=30, cyclomatic_complexity=1, concept_count=1)

    assert 0 < simple < complex_ < 1


# --- Интеграционные тесты: findCorrect и domain-to-rdf через RPC ---


@pytest.fixture(scope="module")
def generated() -> tuple[LearningProblemGeneratorPipeline, list[LearningProblem]]:
    manager = prepare_code(BRANCH_CODE, "python")
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, config=FAST_CONFIG)
    return pipeline, pipeline.run().results()


@pytest.fixture(scope="module")
def templates() -> list[dict[str, Any]]:
    return code_snippet_to_question_templates(
        BRANCH_CODE, config=FAST_CONFIG, origin="test_origin", origin_license="MIT"
    )


def test_statement_registry_is_root_act_with_problem_values(
    generated: tuple[LearningProblemGeneratorPipeline, list[LearningProblem]],
):
    pipeline, problems = generated
    base_values = _condition_values(pipeline.registry)

    for problem in problems:
        statement = problem_statement_registry(pipeline.registry, problem)

        assert len(statement.trace_acts) == 1
        assert _condition_values(statement) == problem.values

    assert _condition_values(pipeline.registry) == base_values


def test_statement_registry_keeps_marker_hints_of_used_values():
    code = textwrap.dedent(
        """
        def fact(n):
            if n <= 1:  # <! (F, "n=3"), (F, "n=2"), (T, "n=1"), (T, "unused") >
                return 1
            return n * fact(n - 1)
        fact(3)
        """
    )
    manager = prepare_code(code, "python")
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, config=FAST_CONFIG)
    [problem] = pipeline.run().results()

    statement = problem_statement_registry(pipeline.registry, problem)

    [condition] = [action for action in statement.all_actions() if action.is_condition]
    assert [value.hint for value in condition.values] == ["n=3", "n=2", "n=1"]


def test_annotated_calls_carry_null_values_into_trace_and_statement():
    code = textwrap.dedent(
        """
        def fact(n):
            if n <= 1:  # <! FFT >
                return 1
            return n * fact(n - 1)  # <! (-, "fact(2)"), (-, "fact(1)"), (-, "unused") >
        fact(3)  # <! (-, "fact(3)") >
        """
    )
    manager = prepare_code(code, "python")
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, config=FAST_CONFIG)
    [problem] = pipeline.run().results()

    # BEGIN-акты вызовов идут в порядке входа, END-акты - в порядке выхода, и каждый
    # несёт значение своего вызова.
    assert _call_act_hints(problem.registry) == {
        "BEGIN": ["fact(3)", "fact(2)", "fact(1)"],
        "END": ["fact(1)", "fact(2)", "fact(3)"],
    }

    # Неизрасходованный хвост срезан, остальное переносится в условие задачи.
    statement = problem_statement_registry(pipeline.registry, problem)
    assert _call_chain_hints(statement) == {
        "BEGIN": [["fact(2)", "fact(1)"], ["fact(3)"]],
        "END": [["fact(1)", "fact(2)"], ["fact(3)"]],
    }


def test_step_out_of_annotated_call_offers_every_call_of_function():
    code = textwrap.dedent(
        """
        def fact(n):
            if n <= 1:  # <! FFT >
                return 1
            return n * fact(n - 1)  # <! (-, "fact(2)"), (-, "fact(1)") >
        fact(3)  # <! (-, "fact(3)") >
        """
    )
    manager = prepare_code(code, "python")
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, config=FAST_CONFIG)
    [problem] = pipeline.run().results()
    statement = problem_statement_registry(pipeline.registry, problem)

    html = render_question_html(statement)
    template = problem_to_question_template(problem, statement, html)

    # Кнопка step-out каждого места вызова предлагает все вызовы функции.
    menus = html.call_value_menus
    assert len(menus) == 2
    for options in menus.values():
        assert sorted(option.hint for option in options) == ["fact(1)", "fact(2)", "fact(3)"]

    # Пункт - отдельный ответ: END кнопки и значение, номер - после номеров кнопок.
    answers = {
        answer["answerId"]: answer
        for answer in template["commonQuestion"]["questionData"]["answerObjects"]
    }
    button_ids = {int(button["action_id"]) for button in html.buttons}
    option_ids = {option.answer_id for options in menus.values() for option in options}
    assert min(option_ids) > max(button_ids)
    for button_id, options in menus.items():
        end_name = answers[button_id]["domainInfo"]
        for option in options:
            assert answers[option.answer_id]["domainInfo"] == option.domain_info
            assert option.domain_info.startswith(f"{end_name},semantic_value_")
            assert answers[option.answer_id]["hyperText"] == option.hint

    soup = BeautifulSoup(html.text, "html.parser")
    custom_buttons = soup.select("[data-comp-ph-custom-click]")
    assert {int(str(tag["id"]).removeprefix("answer_")) for tag in custom_buttons} == set(menus)
    assert {str(tag["id"]) for tag in soup.select(".call-value-menu > button")} == {
        f"answer_{answer_id}" for answer_id in option_ids
    }
    assert soup.select_one("script") is not None


def test_call_end_hints_follow_exit_order_of_sequential_calls():
    code = textwrap.dedent(
        """
        def f(x):
            return x
        for i in range(2):  # <! TTF >
            f(i)  # <! (-, "f(0)"), (-, "f(1)") >
        """
    )
    manager = prepare_code(code, "python")
    pipeline = LearningProblemGeneratorPipeline.from_code(manager, config=FAST_CONFIG)
    [problem] = pipeline.run().results()

    # Невложенные вызовы завершаются в порядке входа.
    assert _call_act_hints(problem.registry) == {
        "BEGIN": ["f(0)", "f(1)"],
        "END": ["f(0)", "f(1)"],
    }
    statement = problem_statement_registry(pipeline.registry, problem)
    assert _call_chain_hints(statement) == {"BEGIN": [["f(0)", "f(1)"]], "END": [["f(0)", "f(1)"]]}


def _call_act_hints(registry: SituationRegistry) -> dict[str, list[str]]:
    """Подсказки значений BEGIN- и END-актов размеченных вызовов в порядке трассы."""
    hints: dict[str, list[str]] = {"BEGIN": [], "END": []}
    for act in registry.trace_acts:
        action = act.action
        if action.annotation is not None and not action.is_condition:
            assert isinstance(act.value, SemanticValue) and act.value.bool_value is None
            hints[action.rule.role].append(act.value.hint)
    return hints


def _call_chain_hints(registry: SituationRegistry) -> dict[str, list[list[str]]]:
    """Подсказки цепочек BEGIN и END размеченных вызовов, по убыванию длины цепочки."""
    chains: dict[str, list[list[str]]] = {"BEGIN": [], "END": []}
    for action in registry.all_actions():
        if action.annotation is not None and not action.is_condition:
            chains[action.rule.role].append([value.hint for value in action.values])
    return {role: sorted(hints, key=len, reverse=True) for role, hints in chains.items()}


def _condition_values(registry: SituationRegistry) -> dict[ActionKey, tuple[bool | None, ...]]:
    return {
        action_key(action): tuple(value.bool_value for value in action.values)
        for action in registry.all_actions()
        if action.is_condition or action.annotation is not None
    }


def test_student_steps_skip_structural_actions(
    generated: tuple[LearningProblemGeneratorPipeline, list[LearningProblem]],
):
    _, problems = generated

    for problem in problems:
        # x = 3, условие, оператор ветви, print; next перед if и вход в ветвь - не шаги.
        assert problem.student_steps == 4
        assert problem.steps > problem.student_steps


def test_templates_match_schema(templates: list[dict[str, Any]]):
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    assert len(templates) == 2
    for template in templates:
        errors = [error.message for error in validator.iter_errors(template)]
        assert errors == []


def test_template_metadata(templates: list[dict[str, Any]]):
    for template in templates:
        [metadata] = template["metadataList"]
        question = template["commonQuestion"]

        assert metadata["domainShortname"] == DOMAIN_SHORTNAME
        assert metadata["version"] == QUESTION_VERSION
        assert metadata["origin"] == "test_origin"
        assert metadata["originLicense"] == "MIT"
        assert metadata["tagBits"] == 8
        assert metadata["solutionSteps"] == 4
        assert metadata["name"] == question["questionData"]["questionName"]
        assert question["tags"] == ["python"]
        assert {"if", "else"} & set(question["concepts"])

    names = [template["metadataList"][0]["name"] for template in templates]
    assert len(set(names)) == len(names)


def test_answer_objects_refer_to_statement_ttl_resources(templates: list[dict[str, Any]]):
    for template in templates:
        data = template["commonQuestion"]["questionData"]
        ttl = data["statementFactsTTL"]
        answer_ids = [answer["answerId"] for answer in data["answerObjects"]]

        assert len(set(answer_ids)) == len(answer_ids)
        for answer in data["answerObjects"]:
            assert re.search(rf"(?m)^:{re.escape(answer['domainInfo'])}\s", ttl)
        # Условие - ситуация до первого шага студента: в трассе только корневой акт.
        assert len(re.findall(r"rdf:type\s+:TraceAct\b", ttl)) == 1
        assert 'class="ctrl-flow-code-block"' in data["questionText"]


def test_templates_without_origin_omit_origin_fields():
    [template, *_] = code_snippet_to_question_templates(BRANCH_CODE, config=FAST_CONFIG)

    metadata = template["metadataList"][0]
    assert "origin" not in metadata
    assert "originLicense" not in metadata


def test_repeated_function_calls_are_exported_with_answer_per_call():
    [template] = code_snippet_to_question_templates(
        "def g(a):\n    return a + 1\n\ng(1)\ng(2)\n", config=FAST_CONFIG
    )

    data = template["commonQuestion"]["questionData"]
    entries = [
        answer["domainInfo"] for answer in data["answerObjects"] if answer["hyperText"] == "step-into"
    ]
    assert len(entries) == 2
    assert len(set(entries)) == 2
    # На каждый вызов: вход, return в теле, выход.
    assert template["metadataList"][0]["solutionSteps"] == 6
