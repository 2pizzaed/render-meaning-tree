"""Данные генерации учебных задач: конфиг, бюджет рассуждателя, метрики и DTO задачи.

Модуль лежит вне пакета ``src.generator.pipeline``: на него ссылается
``src/generator/registry.py``, а импорт из пакета pipeline дал бы цикл.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.generator.registry import SituationRegistry
    from src.generator.value_plan import ActionKey

DEFAULT_SEED = 1806
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "domain"


class BudgetExhausted(Exception):
    """Вызовы рассуждателя или время на фрагмент кончились; сообщение - причина для лога."""


@dataclass
class ReasonerBudget:
    """Общий на все ветки фрагмента бюджет вызовов рассуждателя.

    Основной лимит - число вызовов: он детерминирован. Дедлайн - страховка от медленных
    вызовов, отказ по нему зависит от скорости машины.
    """

    call_limit: int
    time_limit_seconds: float
    calls: int = 0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def exhausted_reason(self) -> str | None:
        if self.calls >= self.call_limit:
            return f"бюджет вызовов рассуждателя исчерпан ({self.call_limit})"
        if self.elapsed_seconds >= self.time_limit_seconds:
            return (
                f"лимит времени фрагмента исчерпан ({self.time_limit_seconds:g} с; "
                "отказ зависит от скорости машины)"
            )
        return None

    def spend_call(self) -> None:
        """Списать один вызов; если бюджет исчерпан, бросить BudgetExhausted."""
        reason = self.exhausted_reason()
        if reason is not None:
            raise BudgetExhausted(reason)
        self.calls += 1


@dataclass(frozen=True, slots=True)
class ProblemGenerationConfig:
    """Параметры генерации задач; значения стартовые, подбираются на корпусе."""

    # Верхняя граница итераций: свободный цикл перебирает {0..N}, do-while - {1..N}.
    max_loop_iterations: int = 4
    # Случайные варианты сверх покрытия исходов (R).
    random_variants: int = 16
    # Сколько вариантов планируется: сначала покрытие, затем случайные (B).
    max_variants: int = 48
    # Максимум непрозрачных действий трассы; он же max_iterations прогона (N_max).
    max_steps: int = 40
    reasoner_call_budget: int = 600
    # Страховочный лимит по времени на фрагмент.
    fragment_time_limit_seconds: float = 180
    reasoner_time_limit_seconds: int = 30
    top_k: int = 15
    selection: Literal["score", "random"] = "score"
    # Вес скиллов в оценке Q.
    alpha: float = 0.7
    # При N = steps_scale оценка уменьшается вдвое (N₀).
    steps_scale: float = 20
    model_dir: Path = DEFAULT_MODEL_DIR
    # Где создавать временные каталоги LOQI веток; None - системный временный каталог.
    temp_root: Path | None = None

    def new_budget(self) -> ReasonerBudget:
        return ReasonerBudget(self.reasoner_call_budget, self.fragment_time_limit_seconds)


@dataclass(frozen=True, slots=True)
class FragmentMetrics:
    cyclomatic_complexity: int
    # Первая непустая строка кода - для логов.
    description: str


@dataclass(frozen=True, slots=True)
class ProblemMetrics:
    # Число непрозрачных действий корректной трассы (N).
    steps: int
    skills: frozenset[str]
    concepts: frozenset[str]
    # Оценка Q; считается при отборе задач фрагмента.
    score: float | None = None


@dataclass(frozen=True, slots=True)
class LearningProblem:
    # Ситуация ветки: код, обрезанные цепочки значений, корректная трасса.
    registry: SituationRegistry
    # Итоговые цепочки значений всех условий.
    values: dict[ActionKey, tuple[bool, ...]]
    steps: int
    skills: frozenset[str]
    concepts: frozenset[str]
    score: float | None
    cyclomatic_complexity: int
    # Описание варианта значений, например ``while@3=2, if@5=else``.
    variant: str
    seed: int
