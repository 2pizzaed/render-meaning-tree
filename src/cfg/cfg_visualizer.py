"""
Модуль для визуализации графов потока управления (CFG) с использованием NetworkX.

Простой и компактный модуль для отображения структуры CFG с информацией о:
- kind узлов (BEGIN, END, и др.)
- ID узлов AST (если доступно)
- constraints на рёбрах (condition_value, interruption_mode)
"""

import matplotlib.pyplot as plt
import networkx as nx
from typing import Optional

from src.cfg.cfg import CFG, Node, Edge, BEGIN, END


def _create_node_label(node: Node) -> str:
    """Создает компактную метку для узла.
    
    Формат: kind\n[AST:id]\n[role]
    """
    parts = []
    
    # Kind узла
    if node.kind:
        parts.append(node.kind)
    
    # AST ID если доступно
    if (node.metadata and 
        node.metadata.wrapped_ast and 
        node.metadata.wrapped_ast.ast_node and
        isinstance(node.metadata.wrapped_ast.ast_node, dict)):
        ast_id = node.metadata.wrapped_ast.ast_node.get('id')
        if ast_id is not None:
            parts.append(f"AST:{ast_id}")
    
    # Role если отличается от kind
    if node.role and node.role != node.kind:
        parts.append(f"role:{node.role}")
    
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
        if edge.constraints.condition_value is True:
            labels.append("T")
        elif edge.constraints.condition_value is False:
            labels.append("F")
    
    # Interruption mode
    if hasattr(edge.constraints, 'interruption_mode') and edge.constraints.interruption_mode:
        mode = edge.constraints.interruption_mode
        if mode == "exception":
            labels.append("exc")
        elif mode == "any":
            labels.append("any")
        else:
            labels.append(str(mode)[:3])  # Обрезаем до 3 символов
    
    return " ".join(labels)


def _build_networkx_graph(cfg: CFG) -> nx.DiGraph:
    """Конвертирует CFG в NetworkX DiGraph.
    
    Добавляет все узлы и рёбра из CFG в NetworkX граф.
    """
    G = nx.DiGraph()
    
    # Добавляем узлы
    for node_id, node in cfg.nodes.items():
        label = _create_node_label(node)
        G.add_node(node_id, label=label, node_obj=node)
    
    # Добавляем рёбра
    for edge in cfg.edges:
        label = _create_edge_label(edge)
        G.add_edge(edge.src, edge.dst, label=label, edge_obj=edge)
    
    return G


def _get_node_color(node: Node) -> str:
    """Определяет цвет узла на основе его kind."""
    if node.role == BEGIN:
        return "lightgreen"  # Зелёный для BEGIN
    elif node.role == END:
        return "lightcoral"  # Красный для END
    else:
        return "lightblue"   # Голубой для обычных узлов


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
        print("Warning: CFG is empty, nothing to visualize")
        return output_file
    
    # 1. Создать NetworkX граф
    G = _build_networkx_graph(cfg)
    
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
        node_obj = G.nodes[node_id]['node_obj']
        node_colors.append(_get_node_color(node_obj))
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                          node_size=2000, alpha=0.8)
    
    # 5. Отрисовать рёбра
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=20, 
                          edge_color='gray', alpha=0.6)
    
    # 6. Отрисовать метки узлов
    node_labels = {node_id: G.nodes[node_id]['label'] 
                   for node_id in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)
    
    # 7. Отрисовать метки рёбер
    edge_labels = {(edge.src, edge.dst): G[edge.src][edge.dst]['label']
                   for edge in cfg.edges
                   if G[edge.src][edge.dst]['label']}  # Только непустые метки
    
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
    from src.cfg.cfg_builder import CFGBuilder
    from src.cfg.abstractions import load_constructs
    
    # Загружаем конструкции
    constructs = load_constructs()
    
    # Создаём простой CFG для демонстрации
    builder = CFGBuilder(constructs)
    simple_cfg = builder._create_simple_cfg("demo")
    
    # Визуализируем
    visualize_cfg(simple_cfg, "demo_cfg.png")
