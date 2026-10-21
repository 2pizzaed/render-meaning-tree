from unittest.mock import Mock

import pytest

from src.generator.problems import BudgetExhausted, ReasonerBudget
from src.helpers.tpg import reasoning


def test_budget_counts_calls_and_stops_at_limit():
    budget = ReasonerBudget(call_limit=2, time_limit_seconds=60)

    budget.spend_call()
    budget.spend_call()

    assert budget.calls == 2
    with pytest.raises(BudgetExhausted, match=r"бюджет вызовов рассуждателя исчерпан \(2\)"):
        budget.spend_call()


def test_budget_deadline_is_reported_as_time_dependent():
    budget = ReasonerBudget(call_limit=10, time_limit_seconds=1)
    budget.started_at -= 5

    assert budget.exhausted_reason() == (
        "лимит времени фрагмента исчерпан (1 с; отказ зависит от скорости машины)"
    )
    with pytest.raises(BudgetExhausted):
        budget.spend_call()
    assert budget.calls == 0


def test_before_iteration_runs_before_reasoner_call_and_can_abort(monkeypatch, tmp_path):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("reasoner must not be called")

    monkeypatch.setattr(reasoning, "_solve_pipeline_reasoning_once", unexpected_call)
    registry = Mock(trace_acts=[])
    budget = ReasonerBudget(call_limit=0, time_limit_seconds=60)

    with pytest.raises(BudgetExhausted):
        reasoning.solve_graph_full_reasoning(
            tmp_path,
            registry,
            model_dir="domain",
            before_iteration=lambda _registry: budget.spend_call(),
        )
