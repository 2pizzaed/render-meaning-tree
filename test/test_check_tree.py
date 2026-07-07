"""Тесты графа проверок ``domain/main.tpg`` (см. docs/check_graph_idea.md).

Каждый сценарий:

1. строит pipeline по фрагменту кода и патчит значения условий (SemanticValue);
2. продвигает частичную трассу прогонами ``findCorrect`` (эталонное поведение
   решателя, как в ``test_solve_tree.py``) до заданного действия;
3. выбирает «действие студента» ``A`` (строка + роль действия);
4. запускает дерево проверок (``main.tpg`` -> дерево по умолчанию) с ``S``/``P``/``A``;
5. проверяет вердикт: ``skill`` из метаданных conclude-узла (извлекается из
   текстовой трассы рассуждателя) и инвариант частичной трассы — после любого
   прогона проверки трасса обязана оставаться префиксом эталонной трассы
   (эталон считается отдельным полным прогоном ``findCorrect`` на свежем
   pipeline с теми же патчами значений).

Выбор действий по (строка, роль) вместо индексов ``line_actions`` сделан
намеренно: роли (``first_cond``, ``if_branch``, ``BEGIN``, ``END``...) заданы
constructs.yml и не зависят от прозрачности/порядка действий на строке.

Языки: основная масса сценариев — Python; C++/Java добавлены для случаев,
которые видны только там (непрозрачные BEGIN/END блоков-скобок:
``construct_not_entered``, ``no_transition`` при закрытии пустого блока).

Кейсы с пометкой «ТРЕБУЕТ ОДОБРЕНИЯ» в комментариях фиксируют фактическое
(проверенное прогоном) поведение графа там, где классификация ошибки может
обсуждаться — ожидания в них стоит пересмотреть вместе с разработчиком.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.generator.helpers import line_actions
from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    SituationDomainDataRegistry,
)
from src.generator.utilities import code_snippet_to_pipeline
from src.helpers.tpg import restore_trace_from_loqi, solve_pipeline_reasoning
from src.model.situation import Action, TraceAct
from src.tpg_domain import ReasoningResult

pytestmark = [pytest.mark.serial, pytest.mark.xdist_group("check_tree")]

FIND_CORRECT_TREE = "findCorrect"
# main.tpg загружается как дерево по умолчанию (normalizeTreeName: "main" -> "");
# отсутствие параметра tree у reasoner-а означает именно его.
CHECK_TREE: str | None = None

MAX_ADVANCE_SOLVES = 80
SOLVE_TIME_LIMIT_SECONDS = 60

# (строка, роль, значения) — выбор действия по роли, см. докстринг модуля.
ValuePatch = tuple[int, str, list[bool]]
# (строка, роль[, имя правила конструкта]) — адрес конкретного действия.
ActionSpec = tuple[int, str] | tuple[int, str, str]
# Сигнатура акта трассы, не зависящая от конкретного pipeline.
TraceSignature = list[tuple[int, str]]

_REFERENCE_CACHE: dict[tuple[str, str, str], TraceSignature] = {}


@dataclass(frozen=True)
class CheckCase:
    """Один сценарий проверки выбора студента.

    ``advance_to``:
      * ``None`` — частичная трасса пуста (P = корневой акт);
      * ``"end"`` — прогнать findCorrect до END всей программы;
      * ``(line, role)`` — прогонять findCorrect, пока P не встанет на это
        действие (``advance_occurrence`` — какая по счёту остановка на нём).
    ``expected_skills`` — допустимые skill вердикта (хотя бы один обязан
    встретиться в трассе проверки); для корректного ответа —
    ``("correct_answer",)`` и ``expected_correct=True``.

    ``action_occurrence`` / ``advance_action_occurrence`` — индекс кандидата,
    когда на строке несколько действий с одинаковой ролью и конструктом
    (например, две ``func`` разных вызовов одной функции).
    """

    id: str
    language: str
    code: str
    action: ActionSpec
    expected_skills: tuple[str, ...]
    expected_correct: bool = False
    action_occurrence: int = 0
    advance_to: ActionSpec | str | None = None
    advance_occurrence: int = 1
    advance_action_occurrence: int = 0
    value_patches: tuple[ValuePatch, ...] = field(default_factory=tuple)


# -- Программы-фикстуры --------------------------------------------------------

PLAIN_STATEMENTS = """
x = 1
y = 2
z = 3
"""

IF_SIMPLE = """
if a > b:
    x = 1
y = 2
"""

IF_TWO_BODY_STATEMENTS = """
if a > b:
    x = 1
    y = 2
z = 3
"""

IF_WITH_ELSE = """
if a > b:
    x = 1
else:
    y = 2
z = 3
"""

WHILE_TWO_ITERATIONS = """
i = 0
while i < 2:
    i = i + 1
x = i
y = 0
"""

FUNCTION_CALL = """
def add(a, b):
    return a + b

x = add(1, 2)
y = x
"""

TWO_SEQUENTIAL_CALLS = """
def f(x):
    return x + 1

a = f(1)
b = f(2)
"""

WHILE_BREAK = """
while flag:
    break
x = 1
"""

NESTED_IFS = """
if a > b:
    if b > c:
        print(c)
x = 1
"""

CPP_IF_BLOCK = """
int a = 1;
if (a > 0) {
    a = 2;
}
int b = a;
"""

JAVA_IF_BLOCK = """
public class Main {
    static void main(String[] args) {
        int x = 0;
        if (x == 0) {
            x = 1;
        }
        x = 2;
    }
}
"""


# -- Сценарии ------------------------------------------------------------------

CHECK_CASES: list[Any] = [
    # --- Линейная последовательность операторов (случай 1.x идеи) ---
    CheckCase(
        id="plain_correct_next",
        language="python",
        code=PLAIN_STATEMENTS,
        advance_to=(1, "first"),
        action=(2, "next"),
        expected_skills=("correct_answer",),
        expected_correct=True,
    ),
    CheckCase(
        # Шаг 2а алгоритма: программа уже полностью вычислена.
        id="plain_everything_evaluated",
        language="python",
        code=PLAIN_STATEMENTS,
        advance_to="end",
        action=(1, "first"),
        expected_skills=("everything_evaluated",),
    ),
    CheckCase(
        # Возврат к уже выполненному оператору (переход назад по цепочке).
        id="plain_action_already_passed",
        language="python",
        code=PLAIN_STATEMENTS,
        advance_to=(2, "next"),
        action=(1, "first"),
        expected_skills=("action_already_passed",),
    ),
    CheckCase(
        # Пропуск оператора между P и A внутри одной цепочки (порядок, 5.2).
        id="plain_actions_order_violated",
        language="python",
        code=PLAIN_STATEMENTS,
        advance_to=(1, "first"),
        action=(3, "next"),
        expected_skills=("actions_order_violated",),
    ),
    # --- Условный оператор ---
    # if_branch в Python раскрывает блок с прозрачным BEGIN, поэтому предпрогонка
    # проходит его автоматически: корректный шаг после истинного условия —
    # первый оператор ветки, а повторный выбор самого if_branch — ошибка.
    CheckCase(
        id="if_correct_enter_body",
        language="python",
        code=IF_SIMPLE,
        advance_to=(1, "first_cond"),
        action=(2, "first"),
        expected_skills=("correct_answer",),
        expected_correct=True,
        value_patches=((1, "first_cond", [True]),),
    ),
    CheckCase(
        # Выбор if_branch, уже пройденного предпрогонкой автоматически:
        # конструкция этого действия сейчас выполняется и не завершена.
        id="if_branch_reselected_after_auto_entry",
        language="python",
        code=IF_SIMPLE,
        advance_to=(1, "first_cond"),
        action=(2, "if_branch"),
        expected_skills=("construct_not_closed",),
        value_patches=((1, "first_cond", [True]),),
    ),
    CheckCase(
        # Условие истинно, студент выбирает вход в else-ветку: переход
        # cond -> else_branch (через to_when_absent) существует, но его
        # ограничение condition_value = false не выполняется (3.1 идеи:
        # «не учтено значение условия»). Предпрогонка здесь останавливается
        # на непрозрачном if_branch, поэтому контекст условия сохраняется.
        id="if_condition_value_not_considered",
        language="python",
        code=IF_WITH_ELSE,
        advance_to=(1, "first_cond"),
        action=(4, "else_branch"),
        expected_skills=("condition_value_not_considered",),
        value_patches=((1, "first_cond", [True]),),
    ),
    CheckCase(
        # Условие ложно, студент выбирает вход в true-ветку: предпрогонка уже
        # прозрачно закрыла if по переходу со значением false, и уточнение
        # autoPassedRefinement возвращает первопричину — значение условия.
        id="if_branch_after_false_condition",
        language="python",
        code=IF_SIMPLE,
        advance_to=(1, "first_cond"),
        action=(2, "if_branch"),
        expected_skills=("condition_value_not_considered",),
        value_patches=((1, "first_cond", [False]),),
    ),
    CheckCase(
        # Выход к оператору после if, когда ветка начата, но не завершена
        # (5.3.2.1: конструкт, раскрытый из D_p, должен быть завершён).
        id="if_construct_not_closed",
        language="python",
        code=IF_TWO_BODY_STATEMENTS,
        advance_to=(2, "first"),
        action=(4, "next"),
        expected_skills=("construct_not_closed",),
        value_patches=((1, "first_cond", [True]),),
    ),
    # --- Цикл while: повторяющиеся действия и цепочки значений ---
    CheckCase(
        # Второе вычисление условия после тела — корректный повтор действия
        # с неиспользованным значением в цепочке.
        id="while_correct_second_condition",
        language="python",
        code=WHILE_TWO_ITERATIONS,
        advance_to=(3, "first"),
        action=(2, "cond"),
        expected_skills=("correct_answer",),
        expected_correct=True,
        value_patches=((2, "cond", [True, True, False]),),
    ),
    CheckCase(
        # Немедленный повтор условия: предпрогонка по истинному значению уже
        # вошла в тело цикла — уточнение autoPassedRefinement объясняет ошибку
        # через значение условия (выполнение уже пошло по другому пути).
        id="while_premature_condition_repeat",
        language="python",
        code=WHILE_TWO_ITERATIONS,
        advance_to=(2, "cond"),
        action=(2, "cond"),
        expected_skills=("condition_value_not_considered",),
        value_patches=((2, "cond", [True, True, False]),),
    ),
    CheckCase(
        # Шаг 2б алгоритма: у действия не осталось неиспользованных значений
        # (цикл уже завершился, все значения условия израсходованы).
        id="while_action_cannot_repeat",
        language="python",
        code=WHILE_TWO_ITERATIONS,
        advance_to=(4, "next"),
        action=(2, "cond"),
        expected_skills=("action_cannot_repeat",),
        value_patches=((2, "cond", [True, True, False]),),
    ),
    # --- Функции (3.2 идеи) ---
    CheckCase(
        # Действие внутри функции, вызов которой ещё не выполнялся.
        id="function_not_entered",
        language="python",
        code=FUNCTION_CALL,
        advance_to=None,
        action=(2, "first"),
        expected_skills=("function_not_entered",),
    ),
    CheckCase(
        # Двухэтапный вход в вызов: после оператора-вызова (content) следующий
        # шаг — BEGIN конструкта вызова (предпрогонка останавливается перед
        # непрозрачным BEGIN, не добавляя его).
        id="function_begin_after_content",
        language="python",
        code=FUNCTION_CALL,
        advance_to=(5, "content"),
        action=(5, "BEGIN", "func_call_structure"),
        expected_skills=("correct_answer",),
        expected_correct=True,
    ),
    CheckCase(
        # Корректный шаг после начала вызова — первый оператор тела функции:
        # переход func и BEGIN тела предпрогонка проходит автоматически
        # (согласовано с эталонными остановками findCorrect).
        id="function_correct_body",
        language="python",
        code=FUNCTION_CALL,
        advance_to=(5, "BEGIN", "func_call_structure"),
        action=(2, "first"),
        expected_skills=("correct_answer",),
        expected_correct=True,
    ),
    CheckCase(
        # Выбор действия func, уже пройденного предпрогонкой автоматически:
        # конструкция вызова сейчас выполняется и не завершена.
        id="function_func_after_auto_entry",
        language="python",
        code=FUNCTION_CALL,
        advance_to=(5, "BEGIN", "func_call_structure"),
        action=(1, "func"),
        expected_skills=("construct_not_closed",),
    ),
    CheckCase(
        # Корректное завершение вызова (выход из функции через END вызова).
        # Пересекает границу функции: роль P на уровнях вне тела разрешается
        # через конструкт определения функции + ослабляющий критерий
        # actAlreadyCurrent (проверено прогоном — работает).
        id="function_correct_exit_call",
        language="python",
        code=FUNCTION_CALL,
        advance_to=(2, "first"),
        action=(5, "END", "func_call_structure"),
        expected_skills=("correct_answer",),
        expected_correct=True,
    ),
    CheckCase(
        # Действие внутри функции, из которой уже вышли.
        id="function_already_exited",
        language="python",
        code=FUNCTION_CALL,
        advance_to=(5, "END", "func_call_structure"),
        action=(2, "first"),
        expected_skills=("function_already_exited",),
    ),
    CheckCase(
        # Повторный вызов той же функции: после BEGIN второго вызова тело
        # снова доступно (повторные активации тела, поиск «в рамках акта E»).
        id="function_second_call_enter",
        language="python",
        code=TWO_SEQUENTIAL_CALLS,
        advance_to=(6, "BEGIN", "func_call_structure"),
        action=(2, "first"),
        expected_skills=("correct_answer",),
        expected_correct=True,
    ),
    CheckCase(
        # Между вызовами тело функции закрыто — вход без нового вызова невозможен.
        id="function_exited_between_calls",
        language="python",
        code=TWO_SEQUENTIAL_CALLS,
        advance_to=(5, "END", "func_call_structure"),
        action=(2, "first"),
        expected_skills=("function_already_exited",),
    ),
    # --- Прерывания ---
    CheckCase(
        # После break студент снова выбирает условие цикла (3.2 идеи):
        # предпрогонка принудительно (актами END без перехода) вывела
        # выполнение из цикла, и уточнение autoPassedRefinement возвращает
        # первопричину — не учтено прерывание.
        id="break_condition_after_break",
        language="python",
        code=WHILE_BREAK,
        advance_to=(2, "first"),
        action=(1, "cond"),
        expected_skills=("interruption_not_considered",),
        value_patches=((1, "cond", [True]),),
    ),
    # --- Вложенные условия (пример из идеи, «конструкты вложены друг в друга») ---
    CheckCase(
        # После истинного внутреннего условия следующий шаг — оператор
        # внутренней ветки (вход в ветку предпрогонка проходит автоматически).
        id="nested_if_correct_inner_body",
        language="python",
        code=NESTED_IFS,
        advance_to=(2, "first_cond"),
        action=(3, "first"),
        expected_skills=("correct_answer",),
        expected_correct=True,
        value_patches=(
            (1, "first_cond", [True]),
            (2, "first_cond", [True]),
        ),
    ),
    CheckCase(
        # Прыжок вглубь через невыполненное внутреннее условие: на одном из
        # уровней иерархии пропущено обязательное действие. Точный skill
        # зависит от прозрачности if_branch — допущены все ошибки «пропуска».
        id="nested_if_skip_inner_condition",
        language="python",
        code=NESTED_IFS,
        advance_to=(1, "first_cond"),
        action=(3, "first"),
        expected_skills=(
            "intermediate_action_skipped",
            "actions_skipped",
            "no_transition",
            "construct_not_entered",
        ),
        value_patches=(
            (1, "first_cond", [True]),
            (2, "first_cond", [True]),
        ),
    ),
    # --- C++: непрозрачные скобки блоков ---
    CheckCase(
        # Прыжок в тело ветки мимо if_branch и открытия блока `{`
        # (BEGIN блока непрозрачен в C++).
        id="cpp_construct_not_entered",
        language="c++",
        code=CPP_IF_BLOCK,
        advance_to=(2, "first_cond"),
        action=(4, "first"),
        expected_skills=("construct_not_entered", "intermediate_action_skipped"),
        value_patches=((2, "first_cond", [True]),),
    ),
    CheckCase(
        # Закрыть блок сразу после открытия, не выполнив тело: перехода
        # BEGIN -> END в непустом блоке нет.
        id="cpp_no_transition_close_empty",
        language="c++",
        code=CPP_IF_BLOCK,
        advance_to=(3, "BEGIN", "block_structure"),
        action=(3, "END", "block_structure"),
        expected_skills=("no_transition", "actions_skipped"),
        value_patches=((2, "first_cond", [True]),),
    ),
    CheckCase(
        # Уйти к оператору после if, не закрыв блок `}`.
        id="cpp_construct_not_closed",
        language="c++",
        code=CPP_IF_BLOCK,
        advance_to=(4, "first"),
        action=(6, "next"),
        expected_skills=("construct_not_closed",),
        value_patches=((2, "first_cond", [True]),),
    ),
    # --- Java: та же семантика скобок + процедурная точка входа ---
    CheckCase(
        # Корректный выбор действия ветки после истинного условия
        # (в Java if_branch — отдельный непрозрачный шаг студента).
        id="java_correct_branch_action",
        language="java",
        code=JAVA_IF_BLOCK,
        advance_to=(2, "first_cond"),
        action=(2, "if_branch"),
        expected_skills=("correct_answer",),
        expected_correct=True,
        value_patches=((2, "first_cond", [True]),),
    ),
    CheckCase(
        # Прыжок в тело ветки мимо if_branch и `{`.
        id="java_construct_not_entered",
        language="java",
        code=JAVA_IF_BLOCK,
        advance_to=(2, "first_cond"),
        action=(3, "first"),
        expected_skills=("construct_not_entered", "intermediate_action_skipped"),
        value_patches=((2, "first_cond", [True]),),
    ),
]


def _case_params() -> list[Any]:
    params: list[Any] = []
    for case in CHECK_CASES:
        if isinstance(case, CheckCase):
            params.append(pytest.param(case, id=case.id))
        else:
            params.append(case)
    return params


# -- Тест ----------------------------------------------------------------------


@pytest.mark.parametrize("case", _case_params())
def test_check_tree(tmp_path: Path, case: CheckCase) -> None:
    reference = _reference_trace_signature(case, tmp_path)

    pipeline, registry = _build_registry(case.code, language=case.language)
    _apply_value_patches(registry, case.value_patches)
    _advance_partial_trace(tmp_path, pipeline, case)

    action = _spec_action(registry, case.action, occurrence=case.action_occurrence)
    before_signature = _trace_signature(registry)
    registry.variables["A"] = action

    result = _run_check(tmp_path, pipeline)

    skills = _extract_skills(result)
    assert not result.exceptions, (
        f"check tree raised reasoner exceptions {result.exceptions}; "
        f"skills={skills}\n{_trace_tail(result)}"
    )

    assert set(case.expected_skills) & set(skills), (
        f"expected one of {case.expected_skills}, got {skills}\n{_trace_tail(result)}"
    )

    if case.expected_correct:
        assert result.result is True, (
            f"expected correct verdict, got {result.result}; skills={skills}\n"
            f"{_trace_tail(result)}"
        )
    else:
        assert result.result is False, (
            f"expected error verdict, got {result.result}; skills={skills}\n"
            f"{_trace_tail(result)}"
        )

    _assert_trace_invariants(
        pipeline,
        result,
        case=case,
        action=action,
        before_signature=before_signature,
        reference=reference,
    )


# -- Построение ситуации -------------------------------------------------------


def _build_registry(
    code: str, *, language: str
) -> tuple[DomainDataGeneratorPipeline, SituationDomainDataRegistry]:
    pipeline = code_snippet_to_pipeline(textwrap.dedent(code), language=language)
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]
    registry.variables["P"] = registry.trace_acts[0]
    return pipeline, registry


def _apply_value_patches(
    registry: SituationDomainDataRegistry,
    patches: tuple[ValuePatch, ...],
) -> None:
    for line_number, role, values in patches:
        _role_action(registry, line_number, role).values = values.copy()


def _spec_action(
    registry: SituationDomainDataRegistry,
    spec: ActionSpec,
    *,
    occurrence: int = 0,
) -> Action:
    line_number, role = spec[0], spec[1]
    construct = spec[2] if len(spec) == 3 else None
    return _role_action(registry, line_number, role, construct, occurrence=occurrence)


def _role_action(
    registry: SituationDomainDataRegistry,
    line_number: int,
    role: str,
    construct: str | None = None,
    *,
    occurrence: int = 0,
) -> Action:
    """Действие на строке по роли правила (включая прозрачные действия).

    ``construct`` — имя правила конструкта (например ``func_call_structure``)
    для строк, где одна роль встречается у нескольких конструктов
    (у оператора с вызовом функции два BEGIN/END: обёртки и самого вызова).
    """
    candidates = [
        action
        for action in line_actions(registry, line_number, include_transparent=True)
        if action.rule.role == role
        and (construct is None or action.parent.rule.name == construct)
    ]
    if occurrence >= len(candidates):
        available = [
            (action.rule.role, action.parent.rule.name)
            for action in line_actions(registry, line_number, include_transparent=True)
        ]
        raise LookupError(
            f"No action with role {role!r} (construct {construct!r}, "
            f"occurrence {occurrence}) on line {line_number}; "
            f"available: {available}"
        )
    return candidates[occurrence]


# -- Продвижение частичной трассы (findCorrect) ---------------------------------


def _advance_partial_trace(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    case: CheckCase,
) -> None:
    if case.advance_to is None:
        return

    registry = pipeline.registry
    target: Action | None = None
    if isinstance(case.advance_to, tuple):
        target = _spec_action(
            registry,
            case.advance_to,
            occurrence=case.advance_action_occurrence,
        )

    stops = 0
    for _iteration in range(MAX_ADVANCE_SOLVES):
        _solve_find_correct_once(tmp_path, pipeline)
        current = registry.variables.get("P")
        current_action = current.action if isinstance(current, TraceAct) else None

        if target is not None and current_action is target:
            stops += 1
            if stops >= case.advance_occurrence:
                return
        if case.advance_to == "end" and _root_end_reached(pipeline, current_action):
            return
        if current_action is not None and _root_end_reached(pipeline, current_action):
            raise AssertionError(
                f"findCorrect reached program END before advance target "
                f"{case.advance_to!r} (occurrence {case.advance_occurrence})"
            )

    raise AssertionError(
        f"advance target {case.advance_to!r} not reached in {MAX_ADVANCE_SOLVES} solves"
    )


def _solve_find_correct_once(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
) -> None:
    with (tmp_path / "find_correct_output.txt").open("a", encoding="utf-8") as out:
        reasoning = solve_pipeline_reasoning(
            tmp_path,
            pipeline,
            model_dir=Path("domain"),
            filename="advance.loqi",
            tree=FIND_CORRECT_TREE,
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=SOLVE_TIME_LIMIT_SECONDS,
            reasoner_output_stream=out,
        )
    assert reasoning.result.result is True and not reasoning.result.exceptions, (
        f"findCorrect failed while advancing the partial trace: {reasoning.result}"
    )
    assert reasoning.exported_loqi is not None, (
        "findCorrect did not export specificDomain"
    )
    assert reasoning.trace_acts, "restored trace is empty"


def _root_end_reached(
    pipeline: DomainDataGeneratorPipeline,
    action: Action | None,
) -> bool:
    if action is None:
        return False
    return (
        action.rule.role == "END"
        and action.parent.rule.name == "global_statements_structure"
    )


# -- Запуск дерева проверок ------------------------------------------------------


def _run_check(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
) -> ReasoningResult:
    with (tmp_path / "check_output.txt").open("a", encoding="utf-8") as out:
        reasoning = solve_pipeline_reasoning(
            tmp_path,
            pipeline,
            model_dir=Path("domain"),
            filename="check.loqi",
            tree=CHECK_TREE,
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=SOLVE_TIME_LIMIT_SECONDS,
            reasoner_output_stream=out,
            restore_exported_trace=False,
        )
    solve_output = reasoning.result
    if solve_output.trace is not None:
        (tmp_path / "check.trace.txt").write_text(
            str(solve_output.trace), encoding="utf-8"
        )
    return solve_output


# -- Вердикт: skill и трасса -----------------------------------------------------


def _extract_skills(result: ReasoningResult) -> list[str]:
    """Все skill, встретившиеся в текстовой трассе выполненных conclude-узлов."""
    trace_text = result.trace if isinstance(result.trace, str) else str(result.trace)
    return re.findall(r"skill=([A-Za-z0-9_]+)", trace_text)


def _trace_tail(result: ReasoningResult, *, lines: int = 40) -> str:
    trace_text = result.trace if isinstance(result.trace, str) else str(result.trace)
    tail = trace_text.splitlines()[-lines:]
    return "--- trace tail ---\n" + "\n".join(tail)


def _trace_signature(registry: SituationDomainDataRegistry) -> TraceSignature:
    return [
        (trace_act.action.ast_id or -1, trace_act.action.rule.role)
        for trace_act in registry.trace_acts
    ]


def _reference_trace_signature(case: CheckCase, tmp_path: Path) -> TraceSignature:
    """Эталонная трасса: полный прогон findCorrect на свежем pipeline."""
    key = (
        case.language,
        case.code,
        repr(sorted(case.value_patches)),
    )
    cached = _REFERENCE_CACHE.get(key)
    if cached is not None:
        return cached

    pipeline, registry = _build_registry(case.code, language=case.language)
    _apply_value_patches(registry, case.value_patches)

    reference_dir = tmp_path / "reference"
    reference_dir.mkdir(exist_ok=True)
    for _iteration in range(MAX_ADVANCE_SOLVES):
        _solve_find_correct_once(reference_dir, pipeline)
        current = registry.variables.get("P")
        current_action = current.action if isinstance(current, TraceAct) else None
        if _root_end_reached(pipeline, current_action):
            break
    else:
        raise AssertionError(
            f"reference findCorrect run did not finish in {MAX_ADVANCE_SOLVES} solves"
        )

    signature = _trace_signature(registry)
    _REFERENCE_CACHE[key] = signature
    return signature


def _assert_trace_invariants(
    pipeline: DomainDataGeneratorPipeline,
    result: ReasoningResult,
    *,
    case: CheckCase,
    action: Action,
    before_signature: TraceSignature,
    reference: TraceSignature,
) -> None:
    exported = result.artifacts.get("specificDomain")
    assert isinstance(exported, str), "check tree did not export specificDomain"
    restore_trace_from_loqi(exported, pipeline)
    after_signature = _trace_signature(pipeline.registry)

    # Проверка никогда не укорачивает трассу; предпрогонка и фиксация ответа
    # обязаны держать её префиксом эталонной трассы (доп. акты — только
    # прозрачные шаги корректного продолжения либо сам корректный ответ).
    assert len(after_signature) >= len(before_signature)
    assert after_signature == reference[: len(after_signature)], (
        "trace diverged from the reference findCorrect trace:\n"
        f"  after:     {after_signature}\n"
        f"  reference: {reference[: len(after_signature)]}"
    )

    appended = after_signature[len(before_signature) :]
    action_signature = (action.ast_id or -1, action.rule.role)
    if case.expected_correct:
        assert action_signature in appended, (
            f"correct verdict must append the chosen action {action_signature}; "
            f"appended acts: {appended}"
        )
    # При error-вердикте добавленные акты допустимы: их персистит предпрогонка
    # (авто-проход прозрачно достижимых действий), а их каноничность уже
    # гарантирована префикс-проверкой выше. Фиксация ответа графом всегда
    # завершается correct, поэтому «коммит при ошибке» невозможен структурно.
