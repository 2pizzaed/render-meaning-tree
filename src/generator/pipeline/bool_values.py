from __future__ import annotations

from src.generator.pipeline.registry import SituationRegistry
from src.model.rules import ActionDeclaration, ConstructDeclaration
from src.model.situation import Action, SemanticValue
from src.pipeline import Pipeline


class BoolValuesPipeline(Pipeline[SituationRegistry]):
    """Ветка генерации bool-значений условий; пока строит один вариант значений."""

    stages = ("assign_values",)

    def assign_values(self) -> None:
        for action in (*self.registry.all_actions(), *self.registry.anonymous_actions):
            action.values = _values_for_action(action)
            action.bind_values()


def _values_for_action(action: Action) -> list[SemanticValue]:
    if action.assumed_value is not None:
        return [SemanticValue(action.assumed_value)]
    return [
        SemanticValue(value)
        for value in _bool_values_for_action(action.rule, action.parent.rule)
    ]


def _bool_values_for_action(
    action_decl: ActionDeclaration, construct_decl: ConstructDeclaration
) -> list[bool]:
    if "condition" not in action_decl.kind:
        return []
    if "loop" in construct_decl.kind_classes:
        return [True, True, False]
    return [True]
