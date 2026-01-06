"""
Альтернативная визуализация CFG через Graphviz (pydot).

Особенности:
- Переиспользует существующую сборку графа из `src.cfg.cfg_visualizer._build_networkx_graph`.
- Сохраняет раскраску узлов через `_get_node_color` (BEGIN/END/обычные).
- Экспортирует в PNG через pydot (требуется установленный системно Graphviz и python-пакет pydot).

Пример использования:

    from src.cfg.cfg_graphviz import visualize_cfg_graphviz
    # output = visualize_cfg_graphviz(cfg, output_file="my_cfg.png", rankdir="LR")

"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
from pydot import Dot

from src.cfg.abstractions import InterruptionType
from src.cfg.cfg import CFG
from src.cfg.cfg_visualizer import (
    _build_networkx_graph,
    _get_node_color,
)
from src.cfg.reachability import PathInfo


def visualize_cfg_graphviz(
    cfg: CFG,
    engine: Literal["dot", "neato", "fdp", "sfdp", "twopi", "circo"] = "dot",
    rankdir: Literal["TB", "BT", "LR", "RL"] = "TB",
    paths_instead_of_edges: bool = False,
    indirect_paths: bool = False,
    paths: list[PathInfo] | None = None,
) -> Dot | None:
    """Визуализирует CFG с помощью Graphviz (pydot), сохраняя PNG.

    Args:
        cfg: Граф потока управления для визуализации.
        output_file: Путь к выходному PNG-файлу.
        engine: Движок layout Graphviz (по умолчанию "dot").
        rankdir: Направление ранжирования (TB/LR/BT/RL).
        paths_instead_of_edges: Если True, визуализировать пути (PathInfo) вместо рёбер.
        indirect_paths: Если True и paths_instead_of_edges=True, визуализировать непрямые пути (is_direct == False).
                       Если False и paths_instead_of_edges=True, визуализировать прямые пути (is_direct == True).

    Returns:
        Путь к сохранённому PNG-файлу.
    """
    if not cfg or not cfg.nodes:
        # Пустой граф — ничего не делаем
        return None

    # 1) Переиспользуем сборку networkx-графа
    G: nx.DiGraph = _build_networkx_graph(cfg, paths_instead_of_edges=paths_instead_of_edges, indirect_paths=indirect_paths, paths=paths)

    # 2) Сформируем «чистый» граф только с сериализуемыми атрибутами,
    #    чтобы избежать проблем nx_pydot с произвольными объектами.
    H: nx.DiGraph = nx.DiGraph()
    for nid in G.nodes:
        H.add_node(nid, label=G.nodes[nid].get('label', str(nid)))
    for src, dst in G.edges:
        edge_data = G[src][dst]
        label = edge_data.get('label', '')
        # Сохраняем информацию о прерываниях для стилизации рёбер
        has_interruption = False

        # Проверяем edge_obj (для обычных рёбер)
        edge_obj = edge_data.get('edge_obj')
        if edge_obj and edge_obj.constraints and edge_obj.constraints.interruption_mode:
            interruption_mode = edge_obj.constraints.interruption_mode
            # Проверяем, есть ли прерывание (не NO_INTERRUPTION, не None)
            if interruption_mode not in (
                None,
                InterruptionType.NO_INTERRUPTION,
            ):
                has_interruption = True

        # Проверяем path_obj (для прямых путей)
        path_obj = edge_data.get('path_obj')
        if path_obj and path_obj.constraints and path_obj.constraints.interruption_mode:
            interruption_mode = path_obj.constraints.interruption_mode
            if interruption_mode not in (
                None,
                InterruptionType.NO_INTERRUPTION,
            ):
                has_interruption = True

        H.add_edge(src, dst, label=label, has_interruption=has_interruption)

    # 3) Конвертируем «чистый» граф в pydot
    p = to_pydot(H)

    # 3) Атрибуты графа/лейаута
    p.set("rankdir", rankdir)
    p.set("splines", "spline")
    p.set("concentrate", "true")
    p.set("layout", engine)

    # 4) Атрибуты узлов (оформление + цвета)
    for n in p.get_nodes():
        # Имена узлов в pydot могут быть в кавычках
        nid = n.get_name().strip('"')
        node_obj = G.nodes[nid].get('node_obj') if nid in G.nodes else None
        n.set_fontname("Helvetica")
        n.set_fontsize("32")
        n.set_shape("box")
        n.set_margin("0.1,0.05")
        n.set_shape("box")
        n.set_style("filled,rounded")
        n.set_fillcolor(_get_node_color(node_obj) if node_obj is not None else "lightgray")

    # 5) Атрибуты рёбер (метки/цвета)
    for e in p.get_edges():
        src = e.get_source().strip('"')
        dst = e.get_destination().strip('"')
        if H.has_edge(src, dst):
            edge_data = H[src][dst]
            lbl = edge_data.get('label', '')
            if lbl:
                e.set_label(lbl)
                e.set_color("gray50")
                e.set_fontname("Helvetica")
                e.set_fontsize("28")
            # Если есть прерывание - делаем ребро пунктирным
            if edge_data.get('has_interruption', False):
                e.set_style("dashed")

    return p


def write_dot(g: Dot | None, output_file: Path) -> None:
    if not g:
        return
    if output_file.suffix.endswith(".png"):
        return g.write_png(str(output_file.absolute()), encoding="utf-8")
    else:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(g.to_string(indent=" ", indent_level=4))


if __name__ == "__main__":
    # Небольшая демонстрация при наличии билдера/конструктов в проекте
    try:
        from src.cfg.abstractions import load_constructs
        from src.cfg.cfg_builder import CFGBuilder

        constructs = load_constructs()
        builder = CFGBuilder(constructs)
        demo_cfg = builder._create_simple_cfg("demo_graphviz")
        g = visualize_cfg_graphviz(demo_cfg, rankdir="LR")
        if g:
            g.write_png("demo_cfg_graphviz.png")
        print("Saved demo_cfg_graphviz.png")
    except Exception as exc:
        # Безопасный фолбэк: демонстрация не критична
        print(f"Demo skipped: {exc}")


