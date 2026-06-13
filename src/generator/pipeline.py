from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from importlib.resources import as_file, files
from typing import Any, Protocol, Self, TypeVar, cast

from src.ast_managers import CodeManager
from src.generator.automaton import ConstructTransitionAutomaton
from src.json_search import JSONPath
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    EffectDeclaration,
    InterruptionType,
    TransitionDeclaration,
    load_construct_declarations,
    locate_construct_declaration_by_ast_node,
)
from src.model.situation import Action, Construct, TraceAct, TraceState
from src.types import Node


class PipelineRegistry(Protocol):
    def collect(self) -> list[Any]: ...


PipelineT = TypeVar("PipelineT", bound="Pipeline")


def pipeline_stage(
    stage_num: int,
) -> Callable[[Callable[[PipelineT], None]], Callable[[PipelineT], None]]:
    def decorator(method: Callable[[PipelineT], None]) -> Callable[[PipelineT], None]:
        method.__pipeline_stage__ = stage_num  # type: ignore
        return method

    return decorator


class Pipeline(ABC):
    def __init__(self):
        self.stage_num = 0
        self.children: list[Self] = []

    def process(self):
        for stage_num, stage in self._iter_stages():
            self.stage_num = stage_num
            stage(self)

    @property
    def current_stage(self) -> int:
        return self.stage_num

    def fork(self) -> Self:
        if not self.can_fork():
            raise RuntimeError("Fork is forbidden for this pipeline")

        child = self._fork()
        self.children.append(child)
        return child

    def can_fork(self) -> bool:
        return True

    @property
    @abstractmethod
    def current_result(self) -> PipelineRegistry: ...

    def flatten_results(self) -> Sequence[PipelineRegistry]:
        result = [self.current_result]
        for child in self.children:
            result.extend(child.flatten_results())
        return result

    @abstractmethod
    def _fork(self) -> Self: ...

    @classmethod
    def _iter_stages(cls) -> list[tuple[int, Callable[[Self], None]]]:
        stages: dict[str, tuple[int, Callable[[Self], None]]] = {}
        for base in reversed(cls.__mro__):
            for name, member in base.__dict__.items():
                stage_num: int | None = getattr(member, "__pipeline_stage__", None)
                if callable(member) and stage_num is not None:
                    stages[name] = (stage_num, member)  # type: ignore
        return sorted(stages.values(), key=lambda item: item[0])


class SituationDomainDataRegistry:
    def __init__(self, owner: DomainDataGeneratorPipeline):
        self.owner = owner
        self.rules: list[ConstructDeclaration] = []
        self.constructs: dict[int, Construct] = {}
        self.actions: dict[int, list[Action]] = {}
        self.anonymous_actions: list[Action] = []
        self.action_orders: dict[int, int] = {}
        self._next_action_order = 0
        self.trace_acts: list[TraceAct] = []
        self.trace_state = TraceState(InterruptionType.NONE)
        self.variables: dict[str, Any] = {"S": self.trace_state}
        self.utilities = set()

    def collect(self) -> list[Any]:
        actions = [action for actions in self.actions.values() for action in actions]
        return [
            *self._used_rules(actions),
            *self.constructs.values(),
            *actions,
            *self.anonymous_actions,
            self.trace_state,
            *self.trace_acts,
            *self.utilities,
        ]

    def get_construct_for(self, ast_id: int) -> Construct | None:
        construct = self.constructs.get(ast_id)
        if construct is not None:
            return construct
        return self.owner._redirected_construct_for(ast_id)

    def get_actions_for(self, ast_id: int | None) -> list[Action]:
        if ast_id is None:
            return self.anonymous_actions.copy()
        return self.actions.get(ast_id, []).copy()

    def get_related_actions(self, construct: Construct) -> list[Action]:
        result = [
            action
            for action in (
                *[action for actions in self.actions.values() for action in actions],
                *self.anonymous_actions,
            )
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
            else [action for actions in self.actions.values() for action in actions]
            + self.anonymous_actions
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

    def copy(self, owner: DomainDataGeneratorPipeline) -> SituationDomainDataRegistry:
        new_registry = SituationDomainDataRegistry(owner)
        new_registry.rules = self.rules.copy()
        new_registry.constructs = self.constructs.copy()
        new_registry.actions = {k: v.copy() for k, v in self.actions.items()}
        new_registry.anonymous_actions = self.anonymous_actions.copy()
        new_registry.action_orders = self.action_orders.copy()
        new_registry._next_action_order = self._next_action_order
        new_registry.trace_acts = self.trace_acts.copy()
        new_registry.trace_state = self.trace_state
        new_registry.variables = self.variables.copy()
        new_registry.utilities = self.utilities.copy()
        return new_registry

    def remember_action_order(self, action: Action) -> None:
        """Запомнить порядок появления action при структурном обходе автомата."""

        if id(action) in self.action_orders:
            return
        self.action_orders[id(action)] = self._next_action_order
        self._next_action_order += 1

    def action_order(self, action: Action) -> int:
        return self.action_orders.get(id(action), self._next_action_order)

    def _action_order_key(self, action: Action) -> tuple[int, int]:
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


class DomainDataGeneratorPipeline(Pipeline):
    def __init__(self, manager: CodeManager, *, fork_enabled: bool = True):
        super().__init__()
        self.manager = manager
        self.registry = SituationDomainDataRegistry(self)
        self.fork_enabled = fork_enabled
        self._redirected_root_construct: Construct | None = None
        self._redirected_root_lookup_ids: set[int] = set()

    @property
    def code(self) -> CodeManager:
        return self.manager

    @property
    def rules(self) -> list[ConstructDeclaration]:
        return self.registry.rules

    @property
    def trace_acts(self) -> list[TraceAct]:
        return self.registry.trace_acts

    @property
    def current_result(self) -> SituationDomainDataRegistry:
        return self.registry

    def flatten_results(self) -> Sequence[SituationDomainDataRegistry]:
        return cast(Sequence[SituationDomainDataRegistry], super().flatten_results())

    def get_construct_for(self, ast_id: int) -> Construct | None:
        return self.registry.get_construct_for(ast_id)

    def _redirected_construct_for(self, ast_id: int) -> Construct | None:
        if ast_id in self._redirected_root_lookup_ids:
            return self._redirected_root_construct
        return None

    def get_actions_for(self, ast_id: int) -> list[Action]:
        return self.registry.get_actions_for(ast_id)

    def get_related_actions(self, construct: Construct) -> list[Action]:
        return self.registry.get_related_actions(construct)

    def _action_order_key(self, action: Action) -> tuple[int, int]:
        # BEGIN/END создаются при Construct.__post_init__, но в цепочке должны
        # обрамлять действия, найденные позже через автомат.
        if action.rule.role == "BEGIN":
            return (0, self.registry.action_order(action))
        if action.rule.role == "END":
            return (2, self.registry.action_order(action))
        return (1, self.registry.action_order(action))

    @property
    def root_rule(self) -> ConstructDeclaration:
        if not self.rules:
            raise RuntimeError("Construct declarations are not loaded")
        return self.rules[0]

    def add(self, object: Any) -> None:
        self.registry.add(object)

    def can_fork(self) -> bool:
        return self.fork_enabled

    def _fork(self) -> Self:
        child = type(self)(self.manager, fork_enabled=False)
        child.registry = self.registry.copy(child)
        return child

    @pipeline_stage(1)
    def _load_rules(self):
        resource = files("src").joinpath("resources", "constructs.yml")
        with as_file(resource) as resource_path:
            self.registry.rules = load_construct_declarations(resource_path)
        self.registry.rules = [
            construct
            for construct in self.registry.rules
            if construct.applicable_to_language(self.manager.language)
        ]

    def _build_construct(self, ast_id: int, node: Node) -> Construct | None:
        if ast_id in self.registry.constructs:
            return self.registry.constructs[ast_id]
        node_type: str = cast(str, node.get("type"))
        construct_decl = locate_construct_declaration_by_ast_node(node_type, self.rules)
        if not construct_decl:
            if node_type != "condition_branch" and self.manager.ast.instanceof(
                ast_id, "statement"
            ):
                warnings.warn(
                    f"No construct declaration found for AST node type {node_type!r} (id: {ast_id})",
                    stacklevel=2,
                )
            return
        if "noop" in construct_decl.kind_classes or construct_decl.is_atomic_inline:
            # конструкты для этих AST структур либо атомарные actions, либо не нужны рассуждателю
            return
        parent = self._build_parent_construct(ast_id)
        if parent is None and construct_decl is not self.root_rule:
            raise ValueError(
                f"Non-root construct {construct_decl.name!r} for AST node {ast_id} has no parent construct"
            )
        self.registry.constructs[ast_id] = Construct(
            parent, ast_id, construct_decl, self
        )
        return self.registry.constructs[ast_id]

    def _build_parent_construct(self, ast_id: int) -> Construct | None:
        par_node = self.code.ast.get_parent_of(ast_id)
        while par_node:
            par_node_id = cast(int | None, par_node.get("id"))
            if par_node_id is None:
                return None
            parent = self._build_construct(par_node_id, par_node)
            if parent is not None:
                return parent
            par_node = self.code.ast.get_parent_of(par_node_id)
        return None

    @pipeline_stage(2)
    def _generate_constructs(self):
        for ast_id, node in self.manager.nodes_cache.items():
            self._build_construct(ast_id, node)

    def _lookup_node_without_identification(
        self, construct: Construct, action_decl: ActionDeclaration
    ) -> Node | None:
        if (node := self.code.ast.get_path(construct.ast_id)) and node.instanceof(
            "function_call"
        ):
            node_content = node.get(self.code.ast)
            assert node_content
            name = cast(
                str,
                cast(dict[str, str], node_content.get("function", {})).get("repr_name"),
            )
            funcs = self.code.user_defined_function_names
            found = funcs.get(name)
            if found:
                return self.code.get_node_by_id(found)
        raise ValueError(
            f"{action_decl.role} in {construct.rule.name} can't be identified"
        )

    def _action_values_for(
        self, action_decl: ActionDeclaration, automaton: ConstructTransitionAutomaton
    ) -> list[bool]:
        """Подобрать возможные значения action-условия на уровне situation.

        Здесь пока задаются только допустимые/дефолтные значения условия.
        Для проверки конкретного числа итераций нужно положить в Action.values
        эталонную последовательность вроде [True, True, False]: ученический
        TraceAct будет проверяться рассуждателем на потребление этих значений.
        assumed_value используется как дефолт правила, например для неявного
        или отсутствующего компонента цикла.
        """

        if automaton.controls_loop(action_decl) and not automaton.repeats_action(
            action_decl
        ):
            return _unique_bool_values(
                value
                for control in automaton.loop_controls()
                if control.action is action_decl
                for value in control.condition_values
            )
        if (
            action_decl.behaviour is not None
            and action_decl.behaviour.assumed_value is not None
        ):
            return [action_decl.behaviour.assumed_value]
        return []

    def _add_action_for_node(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        child: Node,
        automaton: ConstructTransitionAutomaton,
    ) -> Action:
        ast_id = cast(int | None, child.get("id"))
        for existing in self.get_related_actions(construct):
            if existing.ast_id == ast_id and existing.rule is action_decl:
                return existing

        action = Action(
            ast_id=ast_id,
            values=self._action_values_for(action_decl, automaton),
            rule=action_decl,
            parent=construct,
            owner=self,
            effects=self._inline_effects_for_node(child),
        )
        self.add(action)
        return action

    def _inline_effects_for_node(self, node: Node) -> EffectDeclaration | None:
        inline_rule = locate_construct_declaration_by_ast_node(node, self.rules)
        if inline_rule is None or not inline_rule.is_atomic_inline:
            return None
        return inline_rule.effects

    def _resolve_action_node(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        previous_path: JSONPath | None,
    ) -> tuple[Node | None, JSONPath | None]:
        if not action_decl.identification:
            return self._lookup_node_without_identification(
                construct, action_decl
            ), None

        resolved_path = action_decl.identification.resolve_json(
            construct.ast_node,
            previous_path=previous_path,
        )
        child = cast(Node, resolved_path.value) if resolved_path else None
        path = resolved_path.path if resolved_path else None
        return child, path

    @pipeline_stage(3)
    def _fill_actions(self):
        for construct in self.registry.constructs.values():
            self._fill_construct_actions(construct)
        self._promote_procedural_entry_body_to_root()

    def _fill_construct_actions(self, construct: Construct) -> None:
        automaton = ConstructTransitionAutomaton(construct.rule)
        # Структурно обходим граф переходов, передавая JSON path предыдущего
        # action occurrence для identification вида "next".
        queue: deque[tuple[str, str, JSONPath | None, tuple[str, ...]]] = deque()
        for transition in automaton.transitions_from("BEGIN"):
            queue.append((transition.to_role, transition.to_role, None, ()))

        # Одна роль может найтись в нескольких AST path (sequence next / elif),
        # но один и тот же (role, path) нельзя разворачивать бесконечно.
        visited: set[tuple[str, JSONPath | int | None]] = set()
        while queue:
            role, materialize_role, previous_path, fallback_roles = queue.popleft()
            if role in {"BEGIN", "END"}:
                continue

            resolve_decl = automaton.action_by_role(role)
            materialize_decl = automaton.action_by_role(materialize_role)
            child, path = self._resolve_action_node(
                construct, resolve_decl, previous_path
            )
            if child is None:
                # Если основной target отсутствует, идем по to_when_absent от
                # того же предыдущего occurrence.
                queue.extend(
                    (fallback_role, fallback_role, previous_path, ())
                    for fallback_role in fallback_roles
                )
                continue

            action_key = (
                materialize_role,
                path if path is not None else cast(int | None, child.get("id")),
            )
            if action_key in visited:
                continue
            visited.add(action_key)

            if self._is_noop_node(child):
                for transition in automaton.transitions_from(role):
                    absent_roles = _transition_absent_roles(transition)
                    next_role = transition.to_role
                    next_decl = automaton.action_by_role(next_role)
                    next_materialize_role = next_role
                    if (
                        materialize_decl.generalization is not None
                        and materialize_decl.generalization == next_decl.generalization
                    ):
                        next_materialize_role = materialize_role
                    queue.append((next_role, next_materialize_role, path, absent_roles))
                continue

            self._add_action_for_node(construct, materialize_decl, child, automaton)
            for transition in automaton.transitions_from(materialize_role):
                absent_roles = _transition_absent_roles(transition)
                queue.append(
                    (transition.to_role, transition.to_role, path, absent_roles)
                )

    def _is_noop_node(self, node: Node) -> bool:
        matched_rule = locate_construct_declaration_by_ast_node(node, self.rules)
        return matched_rule is not None and "noop" in matched_rule.kind_classes

    def _promote_procedural_entry_body_to_root(self) -> None:
        entry_points = self.code.ast.find_paths_by_type("program_entry_point")
        if not isinstance(entry_points, Sequence) or not entry_points:
            return

        entry_point_path = entry_points[0]
        if not hasattr(entry_point_path, "get") or not hasattr(entry_point_path, "id"):
            return
        entry_point = entry_point_path.get(self.code.ast)
        if not isinstance(entry_point, dict):
            return

        root_construct = self.registry.constructs.get(entry_point_path.id)
        if root_construct is None:
            return
        if any(
            action.is_opaque
            for action in self.registry.get_related_actions(root_construct)
        ):
            return

        entry_node_id = cast(int | None, entry_point.get("entry_point_node_id"))
        if entry_node_id is None:
            return
        entry_node = self.code.get_node_by_id(entry_node_id)
        if not isinstance(entry_node, dict):
            return
        if cast(str | None, entry_node.get("type")) not in {
            "function_definition",
            "method_definition",
        }:
            return

        body_node = cast(Node | None, entry_node.get("body"))
        if not isinstance(body_node, dict):
            return
        body_id = cast(int | None, body_node.get("id"))
        if body_id is None:
            return

        body_construct = self.registry.constructs.get(body_id)
        if body_construct is None:
            return

        self._remove_construct_actions(root_construct)
        self.registry.constructs.pop(entry_point_path.id, None)

        body_construct.rule = self.root_rule
        body_construct.parent = None
        self._rebind_construct_actions(body_construct)

        self._redirected_root_construct = body_construct
        self._redirected_root_lookup_ids = {entry_point_path.id, body_id}

    def _remove_construct_actions(self, construct: Construct) -> None:
        for action in self.registry.get_related_actions(construct):
            if action.ast_id is None:
                self.registry.anonymous_actions = [
                    existing
                    for existing in self.registry.anonymous_actions
                    if existing is not action
                ]
                continue
            actions = self.registry.actions.get(action.ast_id, [])
            filtered = [existing for existing in actions if existing is not action]
            if filtered:
                self.registry.actions[action.ast_id] = filtered
            else:
                self.registry.actions.pop(action.ast_id, None)

    def _rebind_construct_actions(self, construct: Construct) -> None:
        for action in self.registry.get_related_actions(construct):
            rebound_rule = construct.rule.action_declaration_by_role(action.rule.role)
            if rebound_rule is not None:
                action.rule = rebound_rule

    @pipeline_stage(4)
    def _create_default_situation(self):
        entry_point = self.registry.get_construct_for(
            self.code.ast.find_paths_by_type("program_entry_point")[0].id
        )
        assert entry_point, "Unknown entry point"
        self.registry.add(
            TraceAct(
                entry_point.begin_action(),
                entry_point.rule.compiled_transitions_from_role("BEGIN")[0],
                self,
            )
        )

    @pipeline_stage(5)
    def _generate_bool_values(self):
        # TODO: Заглушка, пока не будет нормального анализатора значений
        pass


def _transition_absent_roles(transition: TransitionDeclaration) -> tuple[str, ...]:
    """Нормализовать to_when_absent в кортеж ролей."""

    if transition.to_when_absent is None:
        return ()
    if isinstance(transition.to_when_absent, list):
        return tuple(transition.to_when_absent)
    return (transition.to_when_absent,)


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


def _unique_bool_values(values: Iterable[bool]) -> list[bool]:
    """Сохранить порядок исходов условия и убрать дубли."""

    result: list[bool] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
