"""Значения условий: умолчания и план вариантов для генерации задач."""

from __future__ import annotations

from src.model.situation import Action

DEFAULT_LOOP_VALUES = (True, True, False)
DEFAULT_BRANCH_VALUES = (True,)


def default_condition_values(action: Action) -> tuple[bool, ...]:
    """Цепочка без рассуждателя: разметка, затем assumed_value, затем умолчания."""
    if action.annotation is not None:
        return action.annotation.values
    if action.assumed_value is not None:
        return (action.assumed_value,)
    if not action.is_condition:
        return ()
    if "loop" in action.parent.rule.kind_classes:
        return DEFAULT_LOOP_VALUES
    return DEFAULT_BRANCH_VALUES
