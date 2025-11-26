from collections import defaultdict, deque
from collections.abc import Generator, Sequence
from dataclasses import dataclass, field
import random
import sys
from typing import Iterable

from src.cfg.abstractions import OptionalBoolValue
from src.cfg.cfg import CFG, Node, NodeKind, TraceAct
from src.code_renderer import ButtonType


@dataclass
class UserInteraction:
    ast_node_id: int
    button_type: ButtonType
    atom: bool


def all_interactions(lines_data: list[dict[str, list]]) -> Generator[UserInteraction]:
    for line in lines_data:
        for button in line.get("buttons", []):
            yield UserInteraction(
                ast_node_id=button["node_id"],
                button_type=button["type"],
                atom=button["atom"]
            )


@dataclass
class ConditionDecisionSchedule:
    values: list[bool] = field(default_factory=list)
    fallback: bool | None = None


@dataclass
class TraceScenarioConfig:
    """Настройки генерации трассы для конкретного сценария."""

    name: str = "default"
    condition_sequences: dict[int, ConditionDecisionSchedule | Sequence[bool]] = field(default_factory=dict)
    max_visits_per_node: int = 3
    max_steps: int = 500
    randomize_missing_conditions: bool = True
    seed: int | None = None

    def __post_init__(self):
        normalized: dict[int, ConditionDecisionSchedule] = {}
        for key, schedule in self.condition_sequences.items():
            ast_id = int(key)
            if isinstance(schedule, ConditionDecisionSchedule):
                normalized[ast_id] = schedule
            else:
                normalized[ast_id] = ConditionDecisionSchedule(list(schedule))
        self.condition_sequences = normalized


@dataclass
class VisitedNode:
    node: Node
    condition_value: bool | None = None


@dataclass
class TraceGenerationResult:
    scenario: TraceScenarioConfig
    trace_acts: list[TraceAct]
    terminated_by_limit: bool


class _ConditionDecisionProvider:
    """Хранилище предопределённых значений условий и истории принятых решений."""

    def __init__(self, cfg: CFG, scenario: TraceScenarioConfig):
        self._scenario = scenario
        self._random = random.Random(scenario.seed)
        self._node_sequences: dict[str, deque[bool]] = {}
        self._history: dict[str, list[bool]] = defaultdict(list)
        for node in cfg.nodes.values():
            ast_id = _get_ast_id(node)
            if ast_id is None:
                continue
            schedule = scenario.condition_sequences.get(ast_id)
            if schedule:
                self._node_sequences[node.id] = deque(schedule.values)

    def request(self, node: Node) -> bool | None:
        seq = self._node_sequences.get(node.id)
        if seq and seq:
            return seq.popleft()
        ast_id = _get_ast_id(node)
        schedule = self._scenario.condition_sequences.get(ast_id) if ast_id is not None else None
        if schedule and schedule.fallback is not None:
            return schedule.fallback
        if self._scenario.randomize_missing_conditions:
            return self._random.choice([True, False])
        return False

    def commit(self, node: Node, value: bool | None):
        if value is None:
            return
        self._history[node.id].append(value)

    def history_for(self, node: Node) -> list[bool]:
        return self._history.get(node.id, [])


def generate_trace_variants(cfg: CFG, scenarios: Iterable[TraceScenarioConfig] | None) -> list[TraceGenerationResult]:
    """Генерирует набор трасс для заданных сценариев."""
    scenario_list = list(scenarios) if scenarios else [TraceScenarioConfig()]
    results: list[TraceGenerationResult] = []
    for scenario in scenario_list:
        results.append(_generate_trace_for_scenario(cfg, scenario))
    return results


def _generate_trace_for_scenario(cfg: CFG, scenario: TraceScenarioConfig) -> TraceGenerationResult:
    provider = _ConditionDecisionProvider(cfg, scenario)
    visit_counts: dict[str, int] = defaultdict(int)
    visited_nodes: list[VisitedNode] = []
    current = cfg.begin_node
    steps = 0
    terminated_by_limit = False

    while current and steps < scenario.max_steps:
        steps += 1
        visit_counts[current.id] += 1
        if visit_counts[current.id] > scenario.max_visits_per_node:
            terminated_by_limit = True
            break

        record_index = len(visited_nodes)
        if current.is_mandatory():
            visited_nodes.append(VisitedNode(node=current))

        if current == cfg.end_node:
            break

        next_node, condition_value = _choose_next_node(
            cfg,
            current,
            visit_counts[current.id],
            scenario,
            provider,
        )

        if current.is_mandatory() and record_index < len(visited_nodes):
            visited_nodes[record_index].condition_value = condition_value if current.is_condition() else None

        if not next_node:
            break
        current = next_node

    trace_acts = _visited_to_trace_acts(visited_nodes)
    return TraceGenerationResult(
        scenario=scenario,
        trace_acts=trace_acts,
        terminated_by_limit=terminated_by_limit,
    )


def _choose_next_node(
    cfg: CFG,
    node: Node,
    visit_count: int,
    scenario: TraceScenarioConfig,
    provider: _ConditionDecisionProvider,
) -> tuple[Node | None, bool | None]:
    edges = cfg.edges_from_node(node)
    if not edges:
        return None, None

    if node.is_condition():
        decision = provider.request(node)
        chosen_edge = _edge_for_condition(edges, decision)

        if visit_count >= scenario.max_visits_per_node - 1 and decision is True:
            alternate_edge = _edge_for_condition(edges, False)
            if alternate_edge:
                decision = False
                chosen_edge = alternate_edge

        if chosen_edge is None:
            # fallback to any available edge
            chosen_edge = edges[0]

        provider.commit(node, decision)
        return cfg.nodes.get(chosen_edge.dst), decision

    # Некасательные узлы: выбираем первое ребро
    chosen = edges[0]
    return cfg.nodes.get(chosen.dst), None


def _edge_for_condition(edges: list, decision: bool | None):
    if decision is None:
        return None
    fallback_edge = None
    for edge in edges:
        constraint = edge.constraints.condition_value if edge.constraints else OptionalBoolValue.ANY
        if constraint in (OptionalBoolValue.ANY, OptionalBoolValue.NO_VALUE):
            fallback_edge = fallback_edge or edge
        elif constraint == decision:
            return edge
    return fallback_edge


def _visited_to_trace_acts(visited: list[VisitedNode]) -> list[TraceAct]:
    trace: list[TraceAct] = []
    for record in visited:
        node = record.node
        if not node.metadata.wrapped_ast:
            continue
        trace.append(
            TraceAct(
                wrapped_ast=node.metadata.wrapped_ast,
                cfg_node=node,
                action_spec=node.metadata.abstract_action,
                corresponding_end=None,
                is_known_correct=True,
                condition_value=record.condition_value,
                button_type=_infer_button_type(node),
            )
        )

    for trace_act in trace:
        if trace_act.cfg_node.kind not in {NodeKind.BEGIN, NodeKind.END}:
            continue
        opposite = NodeKind.END if trace_act.cfg_node.kind == NodeKind.BEGIN else NodeKind.BEGIN
        for candidate in trace:
            if (
                candidate.cfg_node.kind == opposite
                and candidate.wrapped_ast
                and trace_act.wrapped_ast
                and candidate.wrapped_ast.ast_node.get("id") == trace_act.wrapped_ast.ast_node.get("id")
            ):
                trace_act.corresponding_end = candidate
                break
    return trace


def _infer_button_type(node: Node) -> str | None:
    if node.is_condition():
        return "question"
    if node.kind == NodeKind.BEGIN:
        return "play"
    if node.kind == NodeKind.END:
        return "stop"
    return "play" if node.is_mandatory() else None


def _get_ast_id(node: Node) -> int | None:
    if node.metadata.wrapped_ast and isinstance(node.metadata.wrapped_ast.ast_node, dict):
        return node.metadata.wrapped_ast.ast_node.get("id")
    return None


def build_trace_act(cfg: CFG, interaction: UserInteraction) -> TraceAct | None:
    for node in cfg.nodes.values():
        if not node.metadata.wrapped_ast or not isinstance(
            node.metadata.wrapped_ast.ast_node, dict
        ):
            continue
        ast_node = node.metadata.wrapped_ast.ast_node
        if ast_node.get("id") != interaction.ast_node_id:
            continue
        match interaction.button_type:
            case "question":
                kind = NodeKind.ATOM
            case "play":
                kind = NodeKind.BEGIN if not interaction.atom else NodeKind.ATOM
            case "step-into":
                kind = NodeKind.BEGIN
            case "stop":
                kind = NodeKind.END
            case "step-out":
                kind = NodeKind.END
            case _:
                raise ValueError(f'Unknown button type: {interaction.button_type}')
                kind = NodeKind.ANY
        if node.kind == kind or (kind != NodeKind.END and node.kind != NodeKind.END):
            return TraceAct(
                    wrapped_ast=node.metadata.wrapped_ast,
                    cfg_node=node,
                    action_spec=node.metadata.abstract_action,
                    corresponding_end=None,
                    is_known_correct=True,
                    condition_value=None,
                    button_type=interaction.button_type
                )
    print(
        f"Warning: No matching node found for interaction: {interaction}",
        file=sys.stderr
    )
    return None


def build_trace_for(cfg: CFG, interactions: list[UserInteraction]) -> list[TraceAct]:
    trace = []
    for interaction in interactions:
        for node in cfg.nodes.values():
            if not node.metadata.wrapped_ast or not isinstance( node.metadata.wrapped_ast.ast_node, dict):
                continue
            ast_node = node.metadata.wrapped_ast.ast_node
            match interaction.button_type:
                case "play":
                    kind = NodeKind.BEGIN
                case "step_into":
                    kind = NodeKind.BEGIN
                case "question":
                    kind = NodeKind.ATOM
                case "step-out", "stop":
                    kind = NodeKind.END
                case _:
                    kind = NodeKind.ANY
            if ast_node.get("id") == interaction.ast_node_id and node.kind == kind:
                trace.append(TraceAct(
                    wrapped_ast=node.metadata.wrapped_ast,
                    cfg_node=node,
                    action_spec=node.metadata.abstract_action,
                    corresponding_end=None,
                    is_known_correct=True,
                    condition_value=None
                ))
    for trace_act in trace:
        if trace_act.cfg_node.kind not in [NodeKind.BEGIN, NodeKind.END]:
            continue
        opposite = NodeKind.END if trace_act.cfg_node.kind == NodeKind.BEGIN else NodeKind.BEGIN
        for potential_end in trace:
            if (potential_end.cfg_node.kind == opposite and
                    potential_end.wrapped_ast.ast_node.get("id") == trace_act.wrapped_ast.ast_node.get("id")):
                trace_act.corresponding_end = potential_end
                break
    assert len(trace) == len(interactions)
    return trace
