"""
Модуль для визуализации графов потока управления (CFG) с использованием NetworkX.

Простой и компактный модуль для отображения структуры CFG с информацией о:
- kind узлов (BEGIN, END, и др.)
- ID узлов AST (если доступно)
- constraints на рёбрах (condition_value, interruption_mode)
"""

import sys
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import networkx as nx
from deprecated import deprecated

from src.cfg.cfg import BEGIN, CFG, END, Edge, Node

if TYPE_CHECKING:
    from src.cfg.reachability import PathInfo


def _create_node_label(node: Node) -> str:
    """Создает компактную метку для узла.
    
    Формат: kind\n[AST:id]\n[role]
    """
    parts = []

    # Kind узла
    if node.kind:
        parts.append(node.kind.value)

    # AST ID если доступно
    if (node.metadata and
        node.metadata.wrapped_ast and
        node.metadata.wrapped_ast.ast_node and
        isinstance(node.metadata.wrapped_ast.ast_node, dict)):
        ast_id = node.metadata.wrapped_ast.ast_node.get('id')
        if ast_id is not None:
            parts.append(f"AST:{ast_id}")

        if node.is_mandatory():
            # parts.append(f"|> " + node.metadata.abstract_action.kind.__str__())
            parts.append(f"|> " + node.metadata.wrapped_ast.ast_node["type"])

    # Role если отличается от kind
    if node.role_in_construct and node.kind and node.role_in_construct != node.kind.value:
        parts.append(f"role:{node.role_in_construct}")

    return '\n'.join(parts) if parts else node.id


def _create_edge_label(edge: Edge) -> str:
    """Создает компактную метку для ребра из constraints.
    
    Извлекает condition_value, interruption_mode и другие constraints.
    Формат: "T", "F", "exc", "any"
    """
    if not edge.constraints:
        return ""

    labels = []

    # Condition value (true/false)
    if hasattr(edge.constraints, 'condition_value') and edge.constraints.condition_value is not None:
        if edge.constraints.condition_value == True:
            labels.append("T")
        elif edge.constraints.condition_value == False:
            labels.append("F")

    # Interruption mode
    if hasattr(edge.constraints, 'interruption_mode') and edge.constraints.interruption_mode:
        mode = edge.constraints.interruption_mode
        if mode == "exception":
            labels.append("exc")
        elif mode == "any":
            pass
            # labels.append("any")
        else:
            labels.append(str(mode)[:3])  # Обрезаем до 3 символов

    return " ".join(labels)


def _create_path_label(path: 'PathInfo') -> str:
    """Создает метку для прямого пути."""
    parts = []

    if getattr(path, "cfg_steps", None):
        parts.append(f"steps:{path.cfg_steps}")

    if getattr(path, "ast_actions", None):
        parts.append(f"ast:{path.ast_actions}")

    if getattr(path, "conditions", None):
        parts.append(f"cond:{path.conditions}")

    if getattr(path, "frame_changes", None):
        parts.append(f"frames:{path.frame_changes}")

    if not parts:
        return ""

    return "\\n".join(parts)


def _build_networkx_graph(cfg: CFG, paths_instead_of_edges=False) -> nx.DiGraph:
    """Конвертирует CFG в NetworkX DiGraph.
    
    Добавляет все узлы и рёбра из CFG в NetworkX граф.
    Безопасно обрабатывает висячие рёбра и несуществующие узлы.
    """
    G = nx.DiGraph()

    # Добавляем узлы
    for node_id, node in cfg.nodes.items():
        label = _create_node_label(node)
        G.add_node(node_id, label=label, node_obj=node)

    direct_paths_added = False

    if paths_instead_of_edges:
        seen_paths: set[str] = set()

        for node in cfg.nodes.values():
            for path in getattr(node, "direct_out_paths", []):
                if path is None or path.is_direct is not True:
                    continue
                if not path.from_ or not path.to_:
                    continue
                path_id = getattr(path, "id", None)
                if path_id:
                    if path_id in seen_paths:
                        continue
                    seen_paths.add(path_id)
                label = _create_path_label(path)
                G.add_edge(path.from_.id, path.to_.id, label=label, path_obj=path, edge_obj=None)
                direct_paths_added = True

    if not direct_paths_added:
        # Добавляем рёбра (только если оба узла существуют)
        for edge in cfg.edges:
            # Проверяем, что оба узла существуют в CFG
            if edge.src in cfg.nodes and edge.dst in cfg.nodes:
                label = _create_edge_label(edge)
                G.add_edge(edge.src, edge.dst, label=label, edge_obj=edge)
            else:
                # Логируем пропущенные рёбра для отладки
                missing_src = edge.src not in cfg.nodes
                missing_dst = edge.dst not in cfg.nodes
                print(
                    f"Skipping edge {edge.src} -> {edge.dst} "
                    f"(missing src: {missing_src}, missing dst: {missing_dst})",
                    file=sys.stderr,
                )

    return G


def _get_node_color(node: Node) -> str:
    """Определяет цвет узла на основе его kind."""
    if node.kind == BEGIN:
        return "lightgreen"  # Зелёный для BEGIN
    elif node.kind == END:
        return "lightcoral"  # Красный для END
    else:
        return "lightblue"   # Голубой для обычных узлов


def diagnose_cfg(cfg: CFG) -> dict:
    """Диагностика проблем в CFG.
    
    Возвращает словарь с информацией о проблемах в графе.
    """
    issues = {
        'orphan_edges': [],
        'missing_nodes': set(),
        'disconnected_nodes': [],
        'total_nodes': len(cfg.nodes),
        'total_edges': len(cfg.edges)
    }

    # Находим висячие рёбра
    for edge in cfg.edges:
        if edge.src not in cfg.nodes:
            issues['orphan_edges'].append(f"Edge {edge.src} -> {edge.dst} (missing src)")
            issues['missing_nodes'].add(edge.src)
        if edge.dst not in cfg.nodes:
            issues['orphan_edges'].append(f"Edge {edge.src} -> {edge.dst} (missing dst)")
            issues['missing_nodes'].add(edge.dst)

    # Находим отключённые узлы
    connected_nodes = set()
    for edge in cfg.edges:
        if edge.src in cfg.nodes and edge.dst in cfg.nodes:
            connected_nodes.add(edge.src)
            connected_nodes.add(edge.dst)

    for node_id in cfg.nodes:
        if node_id not in connected_nodes:
            issues['disconnected_nodes'].append(node_id)

    return issues


@deprecated(reason="Use visualize_cfg_graphviz from src.cfg.cfg_graphviz instead")
def visualize_cfg(cfg: CFG, output_file: str = "cfg.png",
                  layout: str = "spring", figsize: tuple = (12, 8)) -> str:
    """Основная функция визуализации CFG.
    
    Args:
        cfg: Граф потока управления для визуализации
        output_file: Путь к выходному файлу изображения
        layout: Тип размещения узлов ("spring" или "hierarchical")
        figsize: Размер фигуры в дюймах (ширина, высота)
        
    Returns:
        Путь к сохранённому файлу изображения
    """
    if not cfg.nodes:
        print("Warning: CFG is empty, nothing to visualize", file=sys.stderr)
        return output_file

    # 1. Создать NetworkX граф
    G = _build_networkx_graph(cfg)

    # Диагностика проблем в CFG
    issues = diagnose_cfg(cfg)

    if issues['orphan_edges']:
        print(f"Warning: Found {len(issues['orphan_edges'])} orphan edges in CFG:", file=sys.stderr)
        for edge_desc in issues['orphan_edges']:
            print(f"  {edge_desc}")

    if issues['disconnected_nodes']:
        print(f"Warning: Found {len(issues['disconnected_nodes'])} disconnected nodes: {issues['disconnected_nodes']}", file=sys.stderr)

    if issues['missing_nodes']:
        print(
            f"Warning: Missing nodes referenced in edges: {list(issues['missing_nodes'])}",
            file=sys.stderr,
        )
        print(
            f"Warning: Missing nodes referenced in edges: {list(issues['missing_nodes'])}",
            file=sys.stderr,
        )
        print(
            f"Warning: Missing nodes referenced in edges: {list(issues['missing_nodes'])}",
            file=sys.stderr,
        )

    print(f"CFG stats: {issues['total_nodes']} nodes, {issues['total_edges']} edges")

    # 2. Вычислить layout
    if layout == "hierarchical":
        try:
            # Попробуем использовать hierarchical layout
            pos = nx.nx_agraph.graphviz_layout(G, prog='dot')
        except:
            # Fallback к spring layout если graphviz недоступен
            pos = nx.spring_layout(G, seed=42)
    else:  # spring layout
        pos = nx.spring_layout(G, seed=42)

    # 3. Создать фигуру
    plt.figure(figsize=figsize)

    # 4. Отрисовать узлы с цветами
    node_colors = []
    for node_id in G.nodes():
        # Безопасно получаем node_obj
        node_obj = G.nodes[node_id].get('node_obj')
        if node_obj:
            node_colors.append(_get_node_color(node_obj))
        else:
            # Fallback для узлов без node_obj
            node_colors.append("lightgray")

    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                          node_size=2000, alpha=0.8)

    # 5. Отрисовать рёбра
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=20,
                          edge_color='gray', alpha=0.6)

    # 6. Отрисовать метки узлов
    node_labels = {}
    for node_id in G.nodes():
        label = G.nodes[node_id].get('label', node_id)  # Fallback к node_id
        node_labels[node_id] = label
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)

    # 7. Отрисовать метки рёбер
    edge_labels = {}
    for edge in cfg.edges:
        # Проверяем, что рёбро существует в NetworkX графе
        if G.has_edge(edge.src, edge.dst):
            label = G[edge.src][edge.dst].get('label', '')
            if label:  # Только непустые метки
                edge_labels[(edge.src, edge.dst)] = label

    if edge_labels:
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=7)

    # 8. Настройка и сохранение
    plt.title(f"Control Flow Graph: {cfg.name}")
    plt.axis("off")

    # Добавляем легенду
    legend_text = "Green: BEGIN nodes\nRed: END nodes\nBlue: Regular nodes"
    plt.figtext(0.02, 0.02, legend_text, fontsize=10,
                bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.7})

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"CFG visualization saved to: {output_file}")
    return output_file


# Пример использования
if __name__ == "__main__":
    # Демонстрационный пример
    from src.cfg.abstractions import load_constructs
    from src.cfg.cfg_builder import CFGBuilder

    # Загружаем конструкции
    constructs = load_constructs()

    # Создаём простой CFG для демонстрации
    builder = CFGBuilder(constructs)
    simple_cfg = builder._create_simple_cfg("demo")

    # Визуализируем
    visualize_cfg(simple_cfg, "demo_cfg.png")
