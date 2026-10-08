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
from src.generator.value_plan import ValueVariant, action_key
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
        """Шаблон захода вместо умолчания; разметку и assumed_value не трогаем."""
        for key, pattern in self.variant.patterns.items():
            action = self._action(key)
            action.values = [SemanticValue(value) for value in pattern]
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
        with tempfile.TemporaryDirectory(
            prefix=f"problem-{self.variant.index}-", dir=config.temp_root
        ) as directory:
            try:
                solve_graph_full_reasoning(
                    Path(directory),
                    self.registry,
                    model_dir=config.model_dir,
                    tree="findCorrect",
                    max_iterations=config.max_steps,
                    time_limit_seconds=config.reasoner_time_limit_seconds,
                    before_iteration=self._before_reasoner_call,
                )
            except TraceTooLong:
                self.terminate(self._too_long_reason())
            except BudgetExhausted as error:
                self.terminate(str(error))
            except (ReasoningCallError, RuntimeError) as error:
                self.terminate(self._failure_reason(error))

    def trim_values(self) -> None:
        """Срезать неизрасходованные хвосты цепочек.

        Условию, которое ни разу не вычислялось, остаётся первое значение: пустой
        список valueFits трактовал бы как «ограничения нет».
        """
        for key in self.variant.patterns:
            action = self._action(key)
            _trim_values(action, max(action.consumed_value_count(), 1))

        for action in self._annotated_conditions():
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
        self.registry.metrics = ProblemMetrics(
            steps=steps,
            skills=frozenset(collect_skills(ast, trace)),
            concepts=frozenset(collect_concepts(ast, trace)),
        )

    def collect(self) -> LearningProblem:
        registry = self.registry
        metrics = _required(registry.metrics, "metrics")
        return LearningProblem(
            registry=registry,
            values={
                action_key(action): _values_of(action)
                for action in registry.all_actions()
                if action.is_condition
            },
            steps=metrics.steps,
            skills=metrics.skills,
            concepts=metrics.concepts,
            score=metrics.score,
            cyclomatic_complexity=_required(registry.fragment, "fragment").cyclomatic_complexity,
            variant=self.variant.description,
            seed=registry.seed,
        )

    def _before_reasoner_call(self, registry: SituationRegistry) -> None:
        if self._opaque_steps() > self.config.max_steps:
            raise TraceTooLong
        self.budget.spend_call()
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
        # Текст ошибки рассуждателя многострочный: для лога хватает первой строки.
        message = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
        details = "; ".join([message, *getattr(error, "__notes__", [])])
        return f"findCorrect не построил трассу: {details}"

    def _exhausted_annotation(self) -> str | None:
        """Размеченное условие, у которого кончилась цепочка.

        После сбоя registry остаётся в состоянии последней успешной итерации, а за
        вызов условие тратит не больше одного значения. Значит, цепочка, кончившаяся
        во время вызова, в этом состоянии уже израсходована целиком.
        """
        for action in self._annotated_conditions():
            assert action.annotation is not None
            used = action.consumed_value_count()
            if used >= len(action.values):
                return (
                    f"{_line_prefix(action.annotation.line)}цепочка "
                    f"{action.annotation.marker} кончилась на {used + 1}-м вычислении условия"
                )
        return None

    def _too_long_reason(self) -> str:
        return f"трасса длиннее N_max={self.config.max_steps} непрозрачных действий"

    def _opaque_steps(self) -> int:
        return sum(1 for trace_act in self.registry.trace_acts if trace_act.action.is_opaque)

    def _annotated_conditions(self) -> list[Action]:
        return [
            action
            for action in self.registry.all_actions()
            if action.is_condition and action.annotation is not None
        ]

    def _action(self, key: tuple[int | None, str]) -> Action:
        ast_id, role = key
        return self.registry.require_action(ast_id=ast_id, role=role)


def _values_of(action: Action) -> tuple[bool, ...]:
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
