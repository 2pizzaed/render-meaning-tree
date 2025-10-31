from dataclasses import dataclass, field
from typing import Optional, Any, Self

from src.cfg import CFG, Node
from src.cfg.abstractions import DEFAULT_APPEARANCE_PROFILE, AppearanceProfile, AppearanceType, CallStackAction
from src.cfg.cfg import Edge
from src.common_utils import DictLikeDataclass


@dataclass
class PathInfo(DictLikeDataclass):
    """General info about a finite path on CFG.
       Путь по графу: конечный, задаётся двумя узлами и представляет собой кратчайший путь между ними.
       Может замыкаться на одном действии AST, но при этом не будет на самом деле замкнутым, т.к. начало и конец действия обычно представлены различными узлами CFG.
       Узел-источник есть в via_nodes, но не учитывается в подсчёте шагов. Узел-назначение есть в via_nodes и учитывается в подсчёте шагов.
       таким образом, число пройденных рёбер равняется числу пройденных узлов CFG, поэтому пути легко складывать, не производя накладок в точке соединения.
       Важное замечание. Путей между парой точек может быть несколько, но это отражается только в ways_count; остальные метрики учитывают только кратчайший путь.
    """
    # from_: str = None  # id узла
    # to_: str = None  # id узла
    from_: Node  # узел CFG
    to_: Node = None  # узел CFG
    # exists: bool = None  # True, если `ways_count > 0`. False: пути между этой парой улов нет (никакого).
    ways_count: int = 0  # число всевозможных нециклических путей по ориентированному графу CFG между указанными точками (0 - нет никакого пути)
    via_nodes: list[Node] = None  # список id узлов (Node),
    via_edges: list[Edge] = None  # список id ребер (Edge)
    cfg_steps: int = 0  # Число пройденных узлов CFG, без учёта их содержимого = число пройденных рёбер
    ast_actions: int = 0  # Число узлов c непустым AST node на пути
    transparent_actions: int = 0  # Число узлов с заданным AST node, которые считаются "прозрачными" для студента в том смысле, что он с ними не взаимодействует (вариант "может нажать, а может и не нажать" пока не рассматривается)
    opaque_actions: int = 0  # Число узлов с заданным AST node, которые считаются "непрозрачными" для студента в том смысле, что он должен обязательно их нажать, чтобы пройти по пути
    conditions: int = 0  # Число узлов с заданным AST node, которые относятся к непустым управляющим условиям и должны обязательно быть нажаты студентом
    frame_changes: int = 0  # Число смен фрейма функции (могут встречаться как в узлах, так и на рёбрах)
    frames_added: int = 0  # Число входов в функцию (любую)
    frames_dropped: int = 0  # Число выходов из функции (любой)

    def add_step(self, edge: Edge, target_node: Node) -> bool:
        """ returns False if the step cannot be added (no cycles allowed) """
        # validate args compatibility
        assert edge.dst == target_node.id

        if not self.via_nodes or not self.via_edges:
            # init chains
            self.via_nodes = []
            self.via_edges = []
            assert self.from_
            self.via_nodes.append(self.from_)

        # check connectivity with current chain
        # check if the next edge leaves previous node
        assert edge.src == self.via_nodes[-1].id

        if target_node in self.via_nodes:
            return False

        # register new step in chains
        self.via_nodes.append(target_node)
        self.via_edges.append(edge)

        # update all info...
        self.to_ = target_node
        self.cfg_steps = (self.cfg_steps or 0) + 1

        if target_node.metadata.wrapped_ast is not None:
            self.ast_actions = (self.ast_actions or 0) + 1

            # check transparency of this action...
            action = target_node.metadata.abstract_action
            action_kind = action.kind
            if DEFAULT_APPEARANCE_PROFILE.get_appearance_for_kind_chain(action_kind) != AppearanceType.MANDATORY:
                self.transparent_actions = (self.transparent_actions or 0) + 1
            else:
                # mandatory action/button
                self.opaque_actions = (self.opaque_actions or 0) + 1
                # conditions
                if action_kind.has('condition'):
                    self.conditions = (self.conditions or 0) + 1

            # frames
            if action.effects:
                for effect in action.effects:
                    if effect.call_stack:
                        self.frame_changes = (self.frame_changes or 0) + 1
                        if effect.call_stack == CallStackAction.ADD_FRAME:
                            self.frames_added = (self.frames_added or 0) + 1
                        elif effect.call_stack == CallStackAction.DROP_FRAME:
                            self.frames_dropped = (self.frames_dropped or 0) + 1
        return True



def determine_all_paths_through(cfg: CFG, from_: str = None, to_: str = None) -> list[PathInfo]:
    """ 
    Определяет все возможные пути между всеми парами значимых узлов CFG (т.е. узлов, которые ссылаются на непустые AST node).
    При этом пути могут быть циклическими, т.е. начинаться и заканчиваться на одном и том же узле.
    Каждый путь представляет собой список узлов и рёбер, которые проходятся по кратчайшему пути между парой узлов.
    Возвращает список всех путей.

    Реализовано поиском в ширину. После нахождения всех путей выбирать кратчайший, сохранять его и записывать в него число путей.
    """ 
    if not from_:
        from_ = cfg.begin_node.id
    if not to_:
        to_ = cfg.end_node.id

    from_node = cfg.nodes[from_]
    to_node = cfg.nodes[to_]

    wavefront = [
        PathInfo(from_=from_node)
    ]
    targets = {to_node}
    visited = set()
    while wavefront:
        ...



