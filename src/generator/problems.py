"""Данные генерации учебных задач: бюджет рассуждателя.

Модуль лежит вне пакета ``src.generator.pipeline``: на него ссылается
``src/generator/registry.py``, а импорт из пакета pipeline дал бы цикл.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


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
