from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pydot


@dataclass(frozen=True, slots=True)
class DotPalette:
    graph_bg: str = "#fbfbf8"
    node_fill: str = "#fffdf7"
    node_border: str = "#5c4b3b"
    edge_color: str = "#6b7280"
    cluster_fills: tuple[str, ...] = (
        "#fef3c7",
        "#dbeafe",
        "#dcfce7",
        "#fce7f3",
        "#ede9fe",
        "#fae8ff",
    )
    cluster_borders: tuple[str, ...] = (
        "#d97706",
        "#2563eb",
        "#16a34a",
        "#db2777",
        "#7c3aed",
        "#c026d3",
    )
    annotation_fill: str = "#f8fafc"
    annotation_border: str = "#94a3b8"
    transparent_node_fill: str = "#f3f4f6"


DEFAULT_DOT_PALETTE = DotPalette()


def dot_id(value: str, *, prefix: str = "graph") -> str:
    normalized = "".join(
        char if char.isalnum() or char == "_" else "_" for char in value
    )
    if not normalized:
        return prefix
    if normalized[0].isdigit():
        return f"{prefix}_{normalized}"
    return normalized


def dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_dot_png(dot_text: str, path: str | Path) -> Path:
    graphs = pydot.graph_from_dot_data(dot_text)
    if not graphs:
        raise ValueError("Could not render DOT graph")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graphs[0].write_png(str(output_path))  # type: ignore[attr-defined]
    return output_path


class DotDiagram:
    def __init__(
        self,
        name: str,
        *,
        rankdir: str = "LR",
        palette: DotPalette = DEFAULT_DOT_PALETTE,
    ) -> None:
        self.palette = palette
        self.graph = pydot.Dot(
            graph_name=dot_id(name),
            graph_type="digraph",
            rankdir=rankdir,
            bgcolor=palette.graph_bg,
            pad="0.3",
            nodesep="0.45",
            ranksep="0.65",
            splines="spline",
            concentrate="false",
        )
        self.graph.set_node_defaults(
            shape="box",
            style="rounded,filled",
            fontname="Arial",
            fontsize="11",
            color=palette.node_border,
            fillcolor=palette.node_fill,
            penwidth="1.4",
            margin="0.18,0.10",
        )
        self.graph.set_edge_defaults(
            color=palette.edge_color,
            fontname="Arial",
            fontsize="10",
            arrowsize="0.7",
            penwidth="1.2",
        )
        self._clusters: dict[str, pydot.Cluster] = {}

    def add_node(
        self,
        node_id: str,
        *,
        label: str,
        cluster_id: str | None = None,
        **attrs: str,
    ) -> str:
        node = cast(Any, pydot.Node)(node_id, label=label, **attrs)
        if cluster_id is None:
            self.graph.add_node(node)
        else:
            self._clusters[cluster_id].add_node(node)
        return node_id

    def add_edge(self, source: str, target: str, **attrs: str) -> None:
        self.graph.add_edge(cast(Any, pydot.Edge)(source, target, **attrs))

    def ensure_cluster(
        self,
        cluster_id: str,
        *,
        label: str,
        color_index: int = 0,
    ) -> str:
        if cluster_id in self._clusters:
            return cluster_id

        fill = self.palette.cluster_fills[color_index % len(self.palette.cluster_fills)]
        border = self.palette.cluster_borders[
            color_index % len(self.palette.cluster_borders)
        ]
        cluster = cast(Any, pydot.Cluster)(
            cluster_id,
            label=label,
            style="rounded,filled",
            color=border,
            fillcolor=fill,
            fontname="Arial Bold",
            fontsize="12",
            margin="18",
            penwidth="1.8",
        )
        self._clusters[cluster_id] = cluster
        self.graph.add_subgraph(cast(Any, cluster))
        return cluster_id

    def add_cluster_annotation(
        self,
        cluster_id: str,
        *,
        text: str,
        note_id: str,
        anchor_id: str | None = None,
    ) -> str:
        cluster = self._clusters[cluster_id]
        anchor_name = anchor_id or f"{cluster_id}__anchor"
        note_name = note_id
        cluster.add_node(
            cast(Any, pydot.Node)(
                anchor_name,
                label="",
                shape="point",
                width="0.01",
                height="0.01",
                color=self.palette.annotation_border,
            )
        )
        self.graph.add_node(
            cast(Any, pydot.Node)(
                note_name,
                label=text,
                shape="box",
                style="rounded,filled",
                fontname="Courier New",
                fontsize="10",
                color=self.palette.annotation_border,
                fillcolor=self.palette.annotation_fill,
                margin="0.18,0.18",
            )
        )
        self.graph.add_edge(
            cast(Any, pydot.Edge)(
                anchor_name,
                note_name,
                style="dotted",
                arrowhead="none",
                color=self.palette.annotation_border,
            )
        )
        return note_name

    def to_string(self) -> str:
        return self.graph.to_string()

    def write_png(self, path: str | Path) -> Path:
        return render_dot_png(self.to_string(), path)


def multiline_label(*lines: Any) -> str:
    return "\n".join(str(line) for line in lines if line is not None)
