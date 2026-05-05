from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable
from importlib.resources import as_file, files
from typing import Any, Protocol, Self, TypeVar, cast

from src.ast_managers import CodeManager
from src.generator.automaton import ConstructTransitionAutomaton
from src.json_search import JSONPath
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    load_construct_declarations,
    locate_construct_declaration_by_ast_node,
)
from src.model.situation import Action, Construct, TraceAct
from src.types import Node


class PipelineRegistry(Protocol):
    def collect(self) -> list[Any]:
        ...


PipelineT = TypeVar("PipelineT", bound="Pipeline")


def pipeline_stage(stage_num: int) -> \
    Callable[[Callable[[PipelineT], None]], Callable[[PipelineT], None]]:
    def decorator(method: Callable[[PipelineT], None]) -> Callable[[PipelineT], None]:
        method.__pipeline_stage__ = stage_num # type: ignore
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
    def current_result(self) -> PipelineRegistry:
        ...

    def flatten_results(self) -> list[PipelineRegistry]:
        result = [self.current_result]
        for child in self.children:
            result.extend(child.flatten_results())
        return result

    @abstractmethod
    def _fork(self) -> Self:
        ...

    @classmethod
    def _iter_stages(cls) -> list[tuple[int, Callable[[Self], None]]]:
        stages: dict[str, tuple[int, Callable[[Self], None]]] = {}
        for base in reversed(cls.__mro__):
            for name, member in base.__dict__.items():
                stage_num: int | None = getattr(member, "__pipeline_stage__", None)
                if callable(member) and stage_num is not None:
                    stages[name] = (stage_num, member) # type: ignore
        return sorted(stages.values(), key=lambda item: item[0])


class SituationDomainDataRegistry:
    def __init__(self, owner: DomainDataGeneratorPipeline):
        self.owner = owner
        self.constructs: dict[int, Construct] = {}
        self.actions: dict[int, list[Action]] = {}
        self.anonymous_actions: list[Action] = []
        self.trace_acts: list[TraceAct] = []
        self.utilities = set()

    def collect(self) -> list[Any]:
        return [*self.constructs.values(),
                *[action for actions in self.actions.values() for action in actions],
                *self.anonymous_actions,
                *self.trace_acts,
                *self.utilities]

    def copy(self, owner: DomainDataGeneratorPipeline) -> SituationDomainDataRegistry:
        new_registry = SituationDomainDataRegistry(owner)
        new_registry.constructs = self.constructs.copy()
        new_registry.actions = {k: v.copy() for k, v in self.actions.items()}
        new_registry.trace_acts = self.trace_acts.copy()
        new_registry.utilities = self.utilities.copy()
        return new_registry


class DomainDataGeneratorPipeline(Pipeline):
    def __init__(self, manager: CodeManager, *, fork_enabled: bool = True):
        super().__init__()
        self.manager = manager
        self._rules: list[ConstructDeclaration] = []
        self.registry = SituationDomainDataRegistry(self)
        self.fork_enabled = fork_enabled

    @property
    def code(self) -> CodeManager:
        return self.manager

    @property
    def rules(self) -> list[ConstructDeclaration]:
        return self._rules

    @property
    def trace_acts(self) -> list[TraceAct]:
        return self.registry.trace_acts

    @property
    def current_result(self) -> SituationDomainDataRegistry:
        return self.registry

    def get_construct_for(self, ast_id: int) -> Construct | None:
        return self.registry.constructs.get(ast_id)

    def get_actions_for(self, ast_id: int) -> list[Action]:
        return self.registry.actions.get(ast_id, []).copy()

    def get_related_actions(self, construct: Construct) -> list[Action]:
        return [
            action
            for action in (
                *[action for actions in self.registry.actions.values() for action in actions],
                *self.registry.anonymous_actions,
            )
            if action.parent is construct
        ]

    def add(self, object: Any) -> None:
        if isinstance(object, Construct):
            self.registry.constructs[object.ast_id] = object
            return

        if isinstance(object, Action):
            actions = self.registry.actions.setdefault(object.ast_id, []) \
                if object.ast_id is not None else self.registry.anonymous_actions
            if not any(action is object for action in actions):
                actions.append(object)
            return

        if isinstance(object, TraceAct):
            if not any(trace_act is object for trace_act in self.registry.trace_acts):
                self.registry.trace_acts.append(object)
            return

        self.registry.utilities.add(object)

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
            self._rules = load_construct_declarations(resource_path)
        self._rules = [
            construct for construct in self._rules
            if construct.applicable_to_language(self.manager.language)
        ]

    def _build_construct(self, ast_id: int, node: Node) -> Construct | None:
        if ast_id in self.registry.constructs:
            return self.registry.constructs[ast_id]
        node_type: str = cast(str, node.get("type"))
        construct_decl = locate_construct_declaration_by_ast_node(
                 node_type, self.rules)
        if not construct_decl:
            if self.manager.ast.instanceof(ast_id, "statement"):
                warnings.warn(
                    f"No construct declaration found for AST node type {node_type!r} (id: {ast_id})",
                    stacklevel=2)
            return
        if construct_decl.kind_classes.isdisjoint({"noop", "inline"}):
            # конструкты для этих AST структур либо атомарные actions, либо не нужны рассуждателю
            return
        par_node = self.code.ast.get_parent_of(ast_id)
        par_node_id = cast(int, par_node.get("id")) if par_node else None
        self.registry.constructs[ast_id] = Construct(
            self._build_construct(
                par_node_id, par_node
            ) if par_node_id and par_node else None,
            ast_id,
            construct_decl,
            self
        )

    @pipeline_stage(2)
    def _generate_constructs(self):
        for ast_id, node in self.manager.nodes_cache.items():
            self._build_construct(ast_id, node)

    def _lookup_node_without_identification(self, construct: Construct, action_decl: ActionDeclaration) -> Node | None:
        if (node := self.code.ast.get_path(construct.ast_id)) \
            and node.instanceof("function_call"):
            node_content = node.get(self.code.ast)
            assert node_content
            name = cast(str, cast(dict[str, str], node_content.get("function", {})).get("repr_name"))
            funcs = self.code.user_defined_function_names
            found = funcs.get(name)
            if found:
                return self.code.get_node_by_id(found)
        raise ValueError(f"{action_decl.role} in {construct.rule.name} can't be identified")

    def _action_values_for(self, action_decl: ActionDeclaration, automaton: ConstructTransitionAutomaton) -> list[bool]:
        if automaton.controls_loop(action_decl):
            return [True, False] # TODO: пока не готова генерация значений времени выполнения
        if action_decl.behaviour is not None and action_decl.behaviour.assumed_value is not None:
            return [action_decl.behaviour.assumed_value]
        return []

    def _add_action_for_node(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        child: Node,
        automaton: ConstructTransitionAutomaton,
    ) -> None:
        self.add(
            Action(
                ast_id=cast(int | None, child.get("id")),
                values=self._action_values_for(action_decl, automaton),
                rule=action_decl,
                parent=construct,
                owner=self,
            )
        )

    def _resolve_action_node(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        previous_path: JSONPath | None,
    ) -> tuple[Node | None, JSONPath | None]:
        if not action_decl.identification:
            return self._lookup_node_without_identification(construct, action_decl), None

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
            construct_decl = construct.rule
            prev_action_path: JSONPath | None = None
            automaton = ConstructTransitionAutomaton(construct_decl)
            for action_decl in construct_decl.actions:
                if action_decl.role == "BEGIN" or action_decl.role == "END":
                    continue

                while True:
                    child, path = self._resolve_action_node(construct, action_decl, prev_action_path)
                    if child is None:
                        break

                    self._add_action_for_node(construct, action_decl, child, automaton)
                    prev_action_path = path

                    if not automaton.repeats_action(action_decl):
                        break

    @pipeline_stage(4)
    def _generate_bool_values(self):
        # TODO: Заглушка, пока не будет нормального анализатора значений
        pass
