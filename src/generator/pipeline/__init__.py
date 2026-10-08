from __future__ import annotations

import warnings
from collections import deque
from collections.abc import Sequence
from importlib.resources import as_file, files
from typing import Self, cast

from src.ast_managers import CodeManager, NodePathElement
from src.generator.automaton import ConstructTransitionAutomaton
from src.generator.lookup import (
    lookup_function_call_definition,
    lookup_function_call_definition_by_ast_id,
    lookup_next_inline_compound_call_node,
)
from src.generator.registry import SituationRegistry
from src.generator.value_annotations import (
    ValueAnnotationError,
    bind_value_annotations,
)
from src.generator.value_plan import default_condition_values
from src.json_search import JSONPath
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    EffectDeclaration,
    TransitionDeclaration,
    load_construct_declarations,
    locate_construct_declaration_by_ast_node,
)
from src.model.situation import Action, Construct, SemanticValue, TraceAct
from src.pipeline import Pipeline
from src.types import Node, NodeQueryFormat

__all__ = ["LearningProblemGeneratorPipeline"]


class LearningProblemGeneratorPipeline(Pipeline[SituationRegistry]):
    """Строит ситуацию по коду: rules -> конструкты -> actions -> начальная трасса.

    ``run_until("assign_default_values")`` даёт одну ситуацию со значениями условий
    по умолчанию, без рассуждателя.
    """

    stages = (
        "load_rules",
        "generate_constructs",
        "fill_actions",
        "bind_value_annotations",
        "create_default_situation",
        "assign_default_values",
    )

    @classmethod
    def from_code(cls, code: CodeManager) -> Self:
        return cls(SituationRegistry(code=code))

    @property
    def code(self) -> CodeManager:
        return self.registry.code

    @property
    def root_rule(self) -> ConstructDeclaration:
        if not self.registry.rules:
            raise RuntimeError("Construct declarations are not loaded")
        return self.registry.rules[0]

    def load_rules(self) -> None:
        resource = files("src").joinpath("resources", "constructs.yml")
        with as_file(resource) as resource_path:
            self.registry.rules = load_construct_declarations(resource_path)
        self.registry.rules = [
            construct
            for construct in self.registry.rules
            if construct.applicable_to_language(self.code.language)
        ]
        self._patch_rules_for_language()

    def _patch_rules_for_language(self) -> None:
        if self.code.language == "python":
            return

        for construct in self.registry.rules:
            for action in construct.actions:
                if "compound" in action.kind_classes:
                    action.opaque = False
                if (
                    "block" in construct.kind_classes
                    and action.role in {"BEGIN", "END"}
                ):
                    action.opaque = True

    def _build_construct(self, ast_id: int, node: Node) -> Construct | None:
        if ast_id in self.registry.constructs:
            return self.registry.constructs[ast_id]
        node_type: str = cast(str, node.get("type"))
        construct_decl = locate_construct_declaration_by_ast_node(
            node,
            self.registry.rules,
            type_matcher=self._matches_ast_node_type,
        )
        if not construct_decl:
            if node_type != "condition_branch" and self.code.ast.instanceof(
                ast_id, "statement"
            ):
                warnings.warn(
                    f"No construct declaration found for AST node type {node_type!r} (id: {ast_id})",
                    stacklevel=2,
                )
            return
        if not construct_decl.should_build_construct:
            # конструкты для этих AST структур либо атомарные actions, либо не нужны рассуждателю
            return
        if "call" in construct_decl.kind_classes and lookup_function_call_definition_by_ast_id(self.code, ast_id) is None:
                return
        parent = self._build_parent_construct(ast_id)
        if parent is None and construct_decl is not self.root_rule:
            raise ValueError(
                f"Non-root construct {construct_decl.name!r} for AST node {ast_id} has no parent construct"
            )
        self.registry.constructs[ast_id] = Construct(
            parent, ast_id, construct_decl, self.registry
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

    def _matches_ast_node_type(self, node: NodeQueryFormat, node_type: str) -> bool:
        ast_id = cast(int | None, node.get("id"))
        if ast_id is None:
            return False
        return self.code.ast.instanceof(ast_id, node_type)

    def generate_constructs(self) -> None:
        for ast_id, node in self.code.nodes_cache.items():
            self._build_construct(ast_id, node)

    def _lookup_node_without_identification(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        previous_path: JSONPath | None,
    ) -> tuple[Node | None, JSONPath | None]:
        if self._is_inline_compound_construct(construct):
            inline_call_node = lookup_next_inline_compound_call_node(
                construct, previous_path
            )
            return inline_call_node if inline_call_node is not None else (None, None)

        found = lookup_function_call_definition(self.code, construct)
        if found is not None:
            return found, None
        raise ValueError(
            f"{action_decl.role} in {construct.rule.name} can't be identified"
        )

    def _is_inline_compound_construct(self, construct: Construct) -> bool:
        return {"inline", "compound"}.issubset(construct.rule.kind_classes)

    def _add_action_for_node(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        child: Node,
        automaton: ConstructTransitionAutomaton,
    ) -> Action:
        ast_id = cast(int | None, child.get("id"))
        for existing in self.registry.get_related_actions(construct):
            if existing.ast_id == ast_id and existing.rule is action_decl:
                return existing

        action = Action(
            ast_id=ast_id,
            values=[],
            rule=action_decl,
            parent=construct,
            owner=self.registry,
            effects=self._inline_effects_for_node(child),
        )
        self.registry.add(action)
        return action

    def _inline_effects_for_node(self, node: Node) -> EffectDeclaration | None:
        inline_rule = locate_construct_declaration_by_ast_node(
            node,
            self.registry.rules,
            type_matcher=self._matches_ast_node_type,
        )
        if inline_rule is None:
            return None
        # Атомарный inline конструкт не строится, поэтому его эффекты несёт действие.
        # У preorder-конструкта действие выполняется уже после END конструкта, поэтому
        # эффекты конструкта тоже применяются к действию, а не к END (см. rules.py).
        if not inline_rule.is_atomic_inline and not inline_rule.preorder:
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
                construct, action_decl, previous_path
            )

        resolved_path = action_decl.identification.resolve_json(
            construct.ast_node,
            previous_path=previous_path,
        )
        if resolved_path is not None:
            return cast(Node, resolved_path.value), resolved_path.path
        if _has_assumed_value(action_decl):
            return self._lookup_node_without_identification(
                construct, action_decl, previous_path
            )
        return None, None

    def _add_assumed_action(
        self,
        construct: Construct,
        action_decl: ActionDeclaration,
        assumed_value: bool,
    ) -> Action:
        for existing in self.registry.get_related_actions(construct):
            if (
                existing.ast_id == 0
                and existing.rule is action_decl
                and existing.assumed_value == assumed_value
            ):
                return existing

        action = Action(
            ast_id=0,
            values=[SemanticValue(assumed_value)],
            rule=action_decl,
            parent=construct,
            owner=self.registry,
            ast_type="bool_literal",
            assumed_value=assumed_value,
        )
        self.registry.add(action)
        return action

    def fill_actions(self) -> None:
        for construct in self.registry.constructs.values():
            self._fill_construct_actions(construct)
        self._promote_procedural_entry_body_to_root()

    def _fill_construct_actions(self, construct: Construct) -> None:
        automaton = ConstructTransitionAutomaton(construct.rule)
        # Структурно обходим граф переходов, передавая JSON path предыдущего
        # action occurrence для identification вида "next".
        queue: deque[tuple[str, str, JSONPath | None, tuple[str, ...]]] = deque()
        for transition in automaton.transitions_from("BEGIN"):
            queue.append(
                (
                    transition.to_role,
                    transition.to_role,
                    None,
                    _transition_absent_roles(transition),
                )
            )

        # Одна роль может найтись в нескольких AST path (sequence next / elif),
        # но один и тот же (role, path) нельзя разворачивать бесконечно.
        visited: set[tuple[str, JSONPath | int | None]] = set()
        while queue:
            role, materialize_role, previous_path, fallback_roles = queue.popleft()
            if role in {"BEGIN", "END"}:
                continue

            resolve_decl = automaton.action_by_role(role)
            materialize_decl = automaton.action_by_role(materialize_role)
            try:
                child, path = self._resolve_action_node(
                    construct, resolve_decl, previous_path
                )
            except ValueError:
                if not _has_assumed_value(resolve_decl) and not _is_optional_action(
                    resolve_decl
                ):
                    raise
                child, path = None, None
            if child is None:
                assumed_value = _assumed_value(resolve_decl)
                if assumed_value is not None:
                    action_key = (materialize_role, 0)
                    if action_key in visited:
                        continue
                    visited.add(action_key)

                    self._add_assumed_action(
                        construct,
                        materialize_decl,
                        assumed_value,
                    )
                    for transition in automaton.transitions_from(materialize_role):
                        absent_roles = _transition_absent_roles(transition)
                        queue.append(
                            (
                                transition.to_role,
                                transition.to_role,
                                previous_path,
                                absent_roles,
                            )
                        )
                    continue

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

            if self._is_noop_node(child, construct):
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

    def _is_noop_node(self, node: Node, construct: Construct) -> bool:
        matched_rule = locate_construct_declaration_by_ast_node(
            node,
            self.registry.rules,
            type_matcher=self._matches_ast_node_type,
        )
        if matched_rule is None or "noop" not in matched_rule.kind_classes:
            return False
        if "external" in matched_rule.kind_classes:
            return bool({"program", "block"} & construct.rule.kind_classes)
        return True

    def _promote_procedural_entry_body_to_root(self) -> None:
        entry_points = self.code.ast.find_paths_by_type("program_entry_point")
        if not isinstance(entry_points, Sequence) or not entry_points:
            return

        entry_point_path = entry_points[0]
        if not isinstance(entry_point_path, NodePathElement):
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

        self.registry.redirected_root = body_construct
        self.registry.redirected_root_lookup_ids = {entry_point_path.id, body_id}

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

    def bind_value_annotations(self) -> None:
        try:
            bind_value_annotations(self.registry)
        except ValueAnnotationError as error:
            self.terminate(str(error))

    def create_default_situation(self) -> None:
        entry_point = self.registry.get_construct_for(
            self.code.ast.find_paths_by_type("program_entry_point")[0].id
        )
        assert entry_point, "Unknown entry point"
        self.registry.add(
            TraceAct(
                entry_point.begin_action(),
                None,
                self.registry,
            )
        )

    def assign_default_values(self) -> None:
        for action in (*self.registry.all_actions(), *self.registry.anonymous_actions):
            action.values = [
                SemanticValue(value) for value in default_condition_values(action)
            ]
            action.bind_values()


def _transition_absent_roles(transition: TransitionDeclaration) -> tuple[str, ...]:
    """Нормализовать to_when_absent в кортеж ролей."""

    if transition.to_when_absent is None:
        return ()
    if isinstance(transition.to_when_absent, list):
        return tuple(transition.to_when_absent)
    return (transition.to_when_absent,)


def _has_assumed_value(action_decl: ActionDeclaration) -> bool:
    return _assumed_value(action_decl) is not None


def _is_optional_action(action_decl: ActionDeclaration) -> bool:
    return action_decl.is_optional


def _assumed_value(action_decl: ActionDeclaration) -> bool | None:
    return (
        action_decl.behaviour.assumed_value
        if action_decl.behaviour is not None
        else None
    )
