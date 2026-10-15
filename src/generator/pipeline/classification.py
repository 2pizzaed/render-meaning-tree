"""Ветка генерации задач: вариант значений -> корректная трасса -> классификация.

Ветка получает вариант значений (``registry.variant``) и строит по нему корректную
трассу findCorrect. Перед каждым вызовом рассуждателя хук догружает цепочку условия
шаблоном одного захода, если её значения кончились: за вызов условие тратит не больше
одного значения, поэтому цепочка во время вызова не кончается. После трассы
неизрасходованные хвосты срезаются, а задача классифицируется по шагам, скиллам и
концептам.
"""

from __future__ import annotations

import logging
import math
import shutil
import tempfile
from pathlib import Path

from src.generator.concepts import collect_concepts
from src.generator.problems import (
    BudgetExhausted,
    LearningProblem,
    ProblemGenerationConfig,
    ProblemMetrics,
    ReasonerBudget,
)
from src.generator.registry import SituationRegistry
from src.generator.skills import collect_skills
from src.generator.value_annotations import strip_value_markers
from src.generator.value_plan import ActionKey, ValueVariant, action_key
from src.helpers.tpg.reasoning import solve_graph_full_reasoning
from src.model.situation import Action, SemanticValue
from src.pipeline import Pipeline
from src.tpg_domain import ReasoningCallError

logger = logging.getLogger(__name__)


class TraceTooLong(Exception):
    """Трасса уже длиннее N_max: дальнейшие вызовы рассуждателя бесполезны."""


class LearningProblemClassificationPipeline(Pipeline[SituationRegistry]):
    stages = ("assign_values", "solve_correct_trace", "trim_values", "classify")

    @property
    def config(self) -> ProblemGenerationConfig:
        return _required(self.registry.config, "config")

    @property
    def budget(self) -> ReasonerBudget:
        return _required(self.registry.budget, "budget")

    @property
    def variant(self) -> ValueVariant:
        return _required(self.registry.variant, "variant")

    def describe(self) -> str:
        variant = self.registry.variant
        if variant is None:
            return super().describe()
        return f"вариант #{variant.index} ({variant.description})"

    def assign_values(self) -> None:
        """Цепочки варианта на все заходы вместо умолчания; разметку и assumed_value не трогаем."""
        for key, chain in self.variant.chains.items():
            action = self._action(key)
            action.values = [SemanticValue(value) for value in chain]
            action.bind_values()

    def solve_correct_trace(self) -> None:
        reason = self.budget.exhausted_reason()
        if reason is not None:
            self.terminate(reason)
            return

        config = self.config
        # findCorrect продолжает трассу от акта P: в начале это корневой акт.
        self.registry.variables["P"] = self.registry.trace_acts[-1]
        if config.temp_root is not None:
            config.temp_root.mkdir(parents=True, exist_ok=True)
        directory = Path(
            tempfile.mkdtemp(prefix=f"problem-{self.variant.index}-", dir=config.temp_root)
        )
        keep_directory = False
        try:
            solve_graph_full_reasoning(
                directory,
                self.registry,
                model_dir=config.model_dir,
                tree="findCorrect",
                max_iterations=config.max_steps,
                time_limit_seconds=config.reasoner_time_limit_seconds,
                before_iteration=self._before_reasoner_call,
                solver_stops=self.registry.solver_stops,
            )
        except TraceTooLong:
            self.terminate(self._too_long_reason())
        except BudgetExhausted as error:
            self.terminate(str(error))
        except (ReasoningCallError, RuntimeError) as error:
            # LOQI сбойного вызова остаётся для разбора: путь к нему есть в причине.
            keep_directory = True
            self.terminate(self._failure_reason(error))
        finally:
            if not keep_directory:
                shutil.rmtree(directory, ignore_errors=True)

    def trim_values(self) -> None:
        """Срезать неизрасходованные хвосты цепочек.

        Условию, которое ни разу не вычислялось, остаётся первое значение: пустой
        список valueFits трактовал бы как «ограничения нет».
        """
        for key in self.variant.patterns:
            action = self._action(key)
            _trim_values(action, max(action.consumed_value_count(), 1))

        for action in self._annotated_actions():
            assert action.annotation is not None
            used = action.consumed_value_count()
            if used < len(action.values):
                logger.warning(
                    "%s: %sиспользовано %d из %d значений %s",
                    self.describe(),
                    _line_prefix(action.annotation.line),
                    used,
                    len(action.values),
                    action.annotation.marker,
                )
                _trim_values(action, max(used, 1))

    def classify(self) -> None:
        steps = self._opaque_steps()
        if steps > self.config.max_steps:
            self.terminate(self._too_long_reason())
            return
        ast = self.registry.code.ast
        trace = self.registry.trace_acts
        concepts = frozenset(collect_concepts(ast, trace))
        student_steps = len(self._student_step_indexes())
        cyclomatic = _required(self.registry.fragment, "fragment").cyclomatic_complexity
        self.registry.metrics = ProblemMetrics(
            steps=steps,
            student_steps=student_steps,
            skills=frozenset(collect_skills(ast, trace)),
            concepts=concepts,
            complexity=integral_complexity(student_steps, cyclomatic, len(concepts)),
        )

    def collect(self) -> LearningProblem:
        registry = self.registry
        metrics = _required(registry.metrics, "metrics")
        return LearningProblem(
            registry=registry,
            code=strip_value_markers(registry.code),
            values={
                action_key(action): _values_of(action)
                for action in registry.all_actions()
                if action.is_condition or action.annotation is not None
            },
            steps=metrics.steps,
            student_step_indexes=self._student_step_indexes(),
            skills=metrics.skills,
            concepts=metrics.concepts,
            complexity=metrics.complexity,
            score=metrics.score,
            cyclomatic_complexity=_required(registry.fragment, "fragment").cyclomatic_complexity,
            variant_index=self.variant.index,
            variant=self.variant.description,
            seed=registry.seed,
            origin=registry.origin,
        )

    def _before_reasoner_call(self, registry: SituationRegistry) -> None:
        if self._opaque_steps() > self.config.max_steps:
            raise TraceTooLong
        self.budget.spend_call()
        # Страховка: цепочки варианта уже рассчитаны на все заходы, догрузка нужна,
        # только если число заходов неизвестно или оценено неточно.
        for key, pattern in self.variant.patterns.items():
            action = self._action(key)
            if action.consumed_value_count() >= len(action.values):
                action.values.extend(SemanticValue(value) for value in pattern)
                action.bind_values()

    def _failure_reason(self, error: Exception) -> str:
        exhausted = self._exhausted_annotation()
        if exhausted is not None:
            return exhausted
        # Каждая итерация findCorrect кончается шагом студента, поэтому прогон,
        # не дошедший до END за N_max итераций, длиннее N_max.
        if isinstance(error, RuntimeError) and self._opaque_steps() >= self.config.max_steps:
            return self._too_long_reason()
        # Текст ошибки рассуждателя многострочный: для лога хватает первой строки
        # и узла, на котором остановился граф.
        lines = [line.strip() for line in str(error).splitlines() if line.strip()]
        message = lines[0] if lines else type(error).__name__
        if "Final node:" in lines:
            final_node = lines.index("Final node:")
            message += " " + " ".join(lines[final_node : final_node + 3])
        details = "; ".join([message, *getattr(error, "__notes__", [])])
        return f"findCorrect не построил трассу: {details}"

    def _exhausted_annotation(self) -> str | None:
        """Размеченное действие, у которого кончилась цепочка.

        После сбоя registry остаётся в состоянии последней успешной итерации, а за
        вызов рассуждателя действие тратит не больше одного значения. Значит, цепочка,
        кончившаяся во время вызова, в этом состоянии уже израсходована целиком.
        """
        for action in self._annotated_actions():
            assert action.annotation is not None
            used = action.consumed_value_count()
            if used >= len(action.values):
                execution = "вычислении условия" if action.is_condition else "выполнении вызова"
                return (
                    f"{_line_prefix(action.annotation.line)}цепочка "
                    f"{action.annotation.marker} кончилась на {used + 1}-м {execution}"
                )
        return None

    def _too_long_reason(self) -> str:
        return f"трасса длиннее N_max={self.config.max_steps} непрозрачных действий"

    def _student_step_indexes(self) -> tuple[int, ...]:
        """Шаги студента - остановки findCorrect на непрозрачных действиях.

        За вызов findCorrect останавливается на одном шаге студента, а последний вызов -
        на END программы: прозрачный END - признак завершения, а не шаг. Структурные
        непрозрачные действия (``next`` перед ветвлением, ``if_branch``) проходятся
        автоматически и шагами не считаются.
        """
        trace = self.registry.trace_acts
        return tuple(
            index for index in sorted(self.registry.solver_stops) if trace[index].action.is_opaque
        )

    def _opaque_steps(self) -> int:
        return sum(1 for trace_act in self.registry.trace_acts if trace_act.action.is_opaque)

    def _annotated_actions(self) -> list[Action]:
        return [action for action in self.registry.all_actions() if action.annotation is not None]

    def _action(self, key: ActionKey) -> Action:
        construct_ast_id, ast_id, role = key
        return self.registry.require_action(
            ast_id=ast_id, role=role, construct_ast_id=construct_ast_id
        )


def integral_complexity(
    student_steps: int, cyclomatic_complexity: int, concept_count: int
) -> float:
    """Интегральная сложность задачи в (0, 1).

    Линейная модель с прошлой версии генератора (qgen_utils), откалиброванная на
    других метриках: число всех актов трассы, 1 + число условий CFG и прежний набор
    концептов. Здесь в неё подставляются шаги студента, M и концепты текущей
    классификации, поэтому значения сопоставимы только приблизительно.
    """
    score = (
        0.39399354
        + 0.16434003 * (concept_count + 2)
        + 0.01391854 * student_steps
        + 0.05685927 * cyclomatic_complexity
    )
    # Линейная оценка лежит примерно в [1, 3]; сдвиг и масштаб центрируют её для сигмоиды.
    return 1 / (1 + math.exp(-(score - 2) * 5))


def _values_of(action: Action) -> tuple[bool | None, ...]:
    return tuple(value.bool_value for value in action.values)


def _trim_values(action: Action, count: int) -> None:
    # Список меняется на месте: акты трассы ссылаются на его значения.
    del action.values[count:]
    action.bind_values()


def _line_prefix(line: int | None) -> str:
    return f"строка {line}: " if line is not None else ""


def _required[T](value: T | None, name: str) -> T:
    if value is None:
        raise RuntimeError(f"SituationRegistry.{name} is not set")
    return value
