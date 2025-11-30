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

from typing import Literal

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot

from src.cfg.cfg import CFG
from src.cfg.cfg_visualizer import (
    _build_networkx_graph,
    _get_node_color,
)


def visualize_cfg_graphviz(
    cfg: CFG,
    output_file: str = "cfg.png",
    engine: Literal["dot", "neato", "fdp", "sfdp", "twopi", "circo"] = "dot",
    rankdir: Literal["TB", "BT", "LR", "RL"] = "TB",
    paths_instead_of_edges: bool = False,
) -> str:
    """Визуализирует CFG с помощью Graphviz (pydot), сохраняя PNG.

    Args:
        cfg: Граф потока управления для визуализации.
        output_file: Путь к выходному PNG-файлу.
        engine: Движок layout Graphviz (по умолчанию "dot").
        rankdir: Направление ранжирования (TB/LR/BT/RL).
        paths_instead_of_edges: Если True, визуализировать прямые пути (PathInfo) вместо рёбер.

    Returns:
        Путь к сохранённому PNG-файлу.
    """
    if not cfg or not cfg.nodes:
        # Пустой граф — ничего не делаем
        return output_file

    # 1) Переиспользуем сборку networkx-графа
    G: nx.DiGraph = _build_networkx_graph(cfg, paths_instead_of_edges=paths_instead_of_edges)

    # 2) Сформируем «чистый» граф только с сериализуемыми атрибутами,
    #    чтобы избежать проблем nx_pydot с произвольными объектами.
    H: nx.DiGraph = nx.DiGraph()
    for nid in G.nodes:
        H.add_node(nid, label=G.nodes[nid].get('label', str(nid)))
    for src, dst in G.edges:
        H.add_edge(src, dst, label=G[src][dst].get('label', ''))

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

        n.set_shape("box")
        n.set_style("filled,rounded")
        n.set_fillcolor(_get_node_color(node_obj) if node_obj is not None else "lightgray")
        n.set_fontname("Arial")
        n.set_fontsize("10")

    # 5) Атрибуты рёбер (метки/цвета)
    for e in p.get_edges():
        src = e.get_source().strip('"')
        dst = e.get_destination().strip('"')
        if H.has_edge(src, dst):
            lbl = H[src][dst].get('label', '')
            if lbl:
                e.set_label(lbl)
                e.set_fontsize("9")
                e.set_color("gray50")

    # 6) Сохранение PNG
    p.write_png(output_file)
    return output_file


if __name__ == "__main__":
    # Небольшая демонстрация при наличии билдера/конструктов в проекте
    try:
        from src.cfg.cfg_builder import CFGBuilder
        from src.cfg.abstractions import load_constructs

        constructs = load_constructs()
        builder = CFGBuilder(constructs)
        demo_cfg = builder._create_simple_cfg("demo_graphviz")
        visualize_cfg_graphviz(demo_cfg, output_file="demo_cfg_graphviz.png", rankdir="LR")
        print("Saved demo_cfg_graphviz.png")
    except Exception as exc:
        # Безопасный фолбэк: демонстрация не критична
        print(f"Demo skipped: {exc}")


