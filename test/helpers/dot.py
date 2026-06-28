from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from src.dot import (
    DEFAULT_DOT_PALETTE,
    DotDiagram,
    multiline_label,
    render_dot_png,
)
from src.model.rules import InterruptionType
from src.model.situation import Action, Construct, TraceAct
from test.helpers.env import should_output_dot_png, write_text_file


def trace_acts_to_dot(
    trace_acts: Sequence[TraceAct],
    name: str = "trace_acts",
    trace_act_interruptions: Sequence[tuple[int, InterruptionType]] | None = None,
    solver_stops: set[int] | None = None,
) -> str:
    """Построить DOT-граф цепочки TraceAct с группировкой по construct."""
    diagram = DotDiagram(name, palette=DEFAULT_DOT_PALETTE)
    construct_clusters: dict[int, str] = {}
    interruption_modes_by_index: dict[int, InterruptionType] = {
        trace_act_index: interruption_mode
        for trace_act_index, interruption_mode in trace_act_interruptions or ()
    }

    for index, trace_act in enumerate(trace_acts):
        action = trace_act.action
        construct = action.parent
        cluster_id = construct_clusters.get(id(construct))
        if cluster_id is None:
            cluster_index = len(construct_clusters)
            cluster_id = f"cluster_{cluster_index}_{construct.ast_id}"
            construct_clusters[id(construct)] = cluster_id
            diagram.ensure_cluster(
                cluster_id,
                label=f"{construct.rule.name} [{construct.ast_id}]",
                color_index=cluster_index,
            )
            if construct.rule.name != "global_statements_structure":
                diagram.add_cluster_annotation(
                    cluster_id,
                    text=_construct_annotation_text(construct),
                    note_id=f"{cluster_id}__note",
                )

        node_id = f"trace_act_{index}"
        label_parts: list[str] = [
            _trace_action_title(action),
            f"role: {action.rule.role}",
            f"ast_id: {action.ast_id}",
        ]
        if action.rule.role not in ("BEGIN", "END") and action.ast_id is not None:
            action_snippet = construct.owner.code.code_piece(action.ast_id)
            if action_snippet:
                label_parts += ["", _trim_code_snippet(action_snippet)]
        label = multiline_label(*label_parts)
        is_solver_stop = solver_stops is not None and index in solver_stops
        node_attrs = _trace_action_node_attrs(action, solver_stop=is_solver_stop)
        diagram.add_node(
            node_id,
            label=label,
            cluster_id=cluster_id,
            **node_attrs,
        )
        if index > 0:
            edge_attrs: dict[str, str] = {}
            interruption_mode = interruption_modes_by_index.get(index - 1)
            if (
                interruption_mode is not None
                and interruption_mode is not InterruptionType.NONE
            ):
                edge_attrs["label"] = interruption_mode.value
            diagram.add_edge(f"trace_act_{index - 1}", node_id, **edge_attrs)

    return diagram.to_string()


def render_trace_acts_artifacts(
    dir: Path,
    trace_acts: Sequence[TraceAct],
    filename_stem: str = "trace-acts",
    trace_act_interruptions: Sequence[tuple[int, InterruptionType]] | None = None,
    solver_stops: set[int] | None = None,
) -> tuple[Path, Path]:
    """Сохранить DOT и PNG для цепочки TraceAct в указанную директорию."""
    dot_text = trace_acts_to_dot(
        trace_acts,
        name=filename_stem,
        trace_act_interruptions=trace_act_interruptions,
        solver_stops=solver_stops,
    )
    dot_path = write_text_file(dir, dot_text, f"{filename_stem}.dot")
    png_path = dir / f"{filename_stem}.png"
    if should_output_dot_png():
        render_dot_png(dot_text, png_path)
    return dot_path, png_path


def _construct_annotation_text(construct: Construct) -> str:
    snippet = construct.owner.code.code_piece(construct.ast_id) or "<no code snippet>"
    return multiline_label(
        f"ast_id: {construct.ast_id}",
        _trim_code_snippet(snippet),
    )


def _trim_code_snippet(
    snippet: str,
    max_lines: int = 8,
    max_chars: int = 360,
) -> str:
    stripped = snippet.strip()
    if not stripped:
        return "<empty>"
    lines = stripped.splitlines()
    clipped_lines = lines[:max_lines]
    clipped = "\n".join(clipped_lines)
    if len(lines) > max_lines or len(clipped) > max_chars:
        clipped = clipped[:max_chars].rstrip()
        return f"{clipped}\n..."
    return clipped


def _trace_action_title(action: Action) -> str:
    return f"{action.parent.rule.name}.{action.rule.role}"


def _trace_action_node_attrs(
    action: Action, *, solver_stop: bool = False,
) -> dict[str, str]:
    if solver_stop:
        return {
            "fillcolor": "#fef9c3",
            "color": "#b45309",
            "penwidth": "3.0",
            "style": "rounded,filled,bold",
        }
    if action.rule.role == "BEGIN":
        return {"fillcolor": "#e0f2fe", "color": "#0284c7"}
    if action.rule.role == "END":
        return {"fillcolor": "#fee2e2", "color": "#dc2626"}
    if not action.is_opaque:
        return {
            "fillcolor": DEFAULT_DOT_PALETTE.transparent_node_fill,
            "color": "#9ca3af",
            "style": "rounded,filled,dashed",
        }
    return {}
