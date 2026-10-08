from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Self

from src.ast_managers import CodeManager
from src.generator.problems import DEFAULT_SEED
from src.model.rules import ConstructDeclaration, InterruptionType
from src.model.situation import Action, Construct, TraceAct, TraceState
from src.pipeline import PipelineRegistry

if TYPE_CHECKING:
    from src.generator.problems import (
        FragmentMetrics,
        ProblemGenerationConfig,
        ProblemMetrics,
        ReasonerBudget,
    )
    from src.generator.value_plan import ValuePlan, ValueVariant


@dataclass
class SituationRegistry(PipelineRegistry):
    """Объекты одной ситуации; служит SituationContext для Construct/Action/TraceAct."""

    # Бюджет общий: все ветки фрагмента тратят одни вызовы рассуждателя.
    shared: ClassVar[tuple[str, ...]] = ("code", "rules", "config", "budget")

    code: CodeManager
    rules: list[ConstructDeclaration] = field(default_factory=list)
    constructs: dict[int, Construct] = field(default_factory=dict)
    actions: dict[int, list[Action]] = field(default_factory=dict)
    anonymous_actions: list[Action] = field(default_factory=list)
    trace_acts: list[TraceAct] = field(default_factory=list)
    trace_state: TraceState = field(
        default_factory=lambda: TraceState(InterruptionType.NONE)
    )
    variables: dict[str, Any] = field(default_factory=dict)
    utilities: set[Any] = field(default_factory=set)
    # Конструкт тела точки входа, поднятый до корня, и AST id, под которыми он ищется.
    redirected_root: Construct | None = None
    redirected_root_lookup_ids: set[int] = field(default_factory=set)
    # Порядок появления action при структурном обходе автомата, по id(action).
    action_orders: dict[int, int] = field(default_factory=dict)
    _next_action_order: int = 0
    # Генерация задач (см. LearningProblemGeneratorPipeline).
    config: ProblemGenerationConfig | None = None
    budget: ReasonerBudget | None = None
    seed: int = DEFAULT_SEED
    fragment: FragmentMetrics | None = None
    value_plan: ValuePlan | None = None
    variant: ValueVariant | None = None
    metrics: ProblemMetrics | None = None

    def __post_init__(self) -> None:
        self.variables.setdefault("S", self.trace_state)

    def clone(self) -> Self:
        memo = self.shared_memo()
        clone = copy.deepcopy(self, memo)
        # Ключи action_orders - id(action): у клона это id новых объектов из memo.
        clone.action_orders = {
            id(memo[action_id]): order
            for action_id, order in self.action_orders.items()
            if action_id in memo
        }
        return clone

    def domain_objects(self) -> list[Any]:
        """Объекты ситуации для сериализации: использованные rules, затем situation."""
        actions = self.all_actions()
        return [
            *self._used_rules(actions),
            *self.constructs.values(),
            *actions,
            *self.anonymous_actions,
            self.trace_state,
            *self.trace_acts,
            *self.utilities,
        ]

    def all_actions(self) -> list[Action]:
        """Actions с AST id (без anonymous) в порядке добавления узлов."""
        return [action for actions in self.actions.values() for action in actions]

    def get_construct_for(self, ast_id: int) -> Construct | None:
        construct = self.constructs.get(ast_id)
        if construct is not None:
            return construct
        if ast_id in self.redirected_root_lookup_ids:
            return self.redirected_root
        return None

    def get_actions_for(self, ast_id: int | None) -> list[Action]:
        if ast_id is None:
            return self.anonymous_actions.copy()
        return self.actions.get(ast_id, []).copy()

    def get_related_actions(self, construct: Construct) -> list[Action]:
        result = [
            action
            for action in (*self.all_actions(), *self.anonymous_actions)
            if action.parent is construct
        ]
        return sorted(result, key=self._action_order_key)

    def find_actions(
        self,
        *,
        ast_id: int | None = None,
        role: str | None = None,
        construct: Construct | None = None,
        construct_ast_id: int | None = None,
    ) -> list[Action]:
        if construct is None and construct_ast_id is not None:
            construct = self.get_construct_for(construct_ast_id)
            if construct is None:
                return []

        candidates = (
            self.get_actions_for(ast_id)
            if ast_id is not None
            else self.all_actions() + self.anonymous_actions
        )

        return [
            action
            for action in candidates
            if (role is None or action.rule.role == role)
            and (construct is None or action.parent is construct)
        ]

    def require_action(
        self,
        *,
        ast_id: int | None = None,
        role: str | None = None,
        construct: Construct | None = None,
        construct_ast_id: int | None = None,
    ) -> Action:
        matches = self.find_actions(
            ast_id=ast_id,
            role=role,
            construct=construct,
            construct_ast_id=construct_ast_id,
        )
        if len(matches) != 1:
            conditions = _format_lookup_conditions(
                ast_id=ast_id,
                role=role,
                construct=construct,
                construct_ast_id=construct_ast_id,
            )
            raise LookupError(
                f"Expected exactly one action for {conditions}, found {len(matches)}"
            )
        return matches[0]

    def add(self, object: Any) -> None:
        if isinstance(object, Construct):
            self.constructs[object.ast_id] = object
            return

        if isinstance(object, Action):
            actions = (
                self.actions.setdefault(object.ast_id, [])
                if object.ast_id is not None
                else self.anonymous_actions
            )
            if not any(action is object for action in actions):
                actions.append(object)
            self.remember_action_order(object)
            return

        if isinstance(object, TraceAct):
            if not any(trace_act is object for trace_act in self.trace_acts):
                self.trace_acts.append(object)
            return

        if isinstance(object, TraceState):
            previous_trace_state = self.trace_state
            self.trace_state = object
            self.variables = {
                name: object if value is previous_trace_state else value
                for name, value in self.variables.items()
            }
            self.variables.setdefault("S", object)
            return

        self.utilities.add(object)

    def remember_action_order(self, action: Action) -> None:
        """Запомнить порядок появления action при структурном обходе автомата."""

        if id(action) in self.action_orders:
            return
        self.action_orders[id(action)] = self._next_action_order
        self._next_action_order += 1

    def action_order(self, action: Action) -> int:
        return self.action_orders.get(id(action), self._next_action_order)

    def _action_order_key(self, action: Action) -> tuple[int, int]:
        # BEGIN/END создаются при Construct.__post_init__, но в цепочке должны
        # обрамлять действия, найденные позже через автомат.
        if action.rule.role == "BEGIN":
            return (0, self.action_order(action))
        if action.rule.role == "END":
            return (2, self.action_order(action))
        return (1, self.action_order(action))

    def _used_rules(self, actions: list[Action]) -> list[ConstructDeclaration]:
        """Вернуть только rules, реально использованные объектами situation."""

        used_rule_ids = {id(construct.rule) for construct in self.constructs.values()}
        used_rule_ids.update(
            id(action.rule.parent)
            for action in (*actions, *self.anonymous_actions)
            if action.rule.parent is not None
        )
        used_rule_ids.update(
            id(trace_act.used_transition.parent)
            for trace_act in self.trace_acts
            if trace_act.used_transition is not None
            and trace_act.used_transition.parent is not None
        )
        return [rule for rule in self.rules if id(rule) in used_rule_ids]


def _format_lookup_conditions(
    *,
    ast_id: int | None,
    role: str | None,
    construct: Construct | None,
    construct_ast_id: int | None,
) -> str:
    parts: list[str] = []
    if ast_id is not None:
        parts.append(f"ast_id={ast_id!r}")
    if role is not None:
        parts.append(f"role={role!r}")
    if construct is not None:
        parts.append(f"construct_ast_id={construct.ast_id!r}")
    elif construct_ast_id is not None:
        parts.append(f"construct_ast_id={construct_ast_id!r}")
    return ", ".join(parts) if parts else "no conditions"
