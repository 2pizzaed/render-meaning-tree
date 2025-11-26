from collections.abc import Generator
from dataclasses import dataclass
import sys

from src.cfg.cfg import CFG, NodeKind, TraceAct
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
