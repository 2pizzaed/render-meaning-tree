import copy
from collections import defaultdict
from dataclasses import dataclass, field
from warnings import deprecated

from src.cfg import CFG, Edge, Node
from src.cfg.abstractions import (
    CallStackAction,
    Constraints,
    Effects,
    InterruptionType, WithEffectsMixin,
)
from src.cfg.cfg import idgen
from src.common_utils import DictLikeDataclass


@dataclass
class PathInfo(DictLikeDataclass, WithEffectsMixin):
    """General info about a finite path on CFG.
       Путь по графу: конечный, задаётся двумя узлами и представляет собой кратчайший путь между ними.
       Может замыкаться на одном действии AST, но при этом не будет на самом деле замкнутым, т.к. начало и конец действия обычно представлены различными узлами CFG.
       Узел-источник есть в via_nodes, но не учитывается в подсчёте шагов. Узел-назначение есть в via_nodes и учитывается в подсчёте шагов.
       Таким образом, число пройденных рёбер равняется числу пройденных узлов CFG, поэтому пути легко складывать, не производя накладок в точке соединения.
    """
    from_: Node  # узел CFG
    to_: Node = None  # узел CFG
    is_direct: bool | None = None  # True, если путь между парой непрозрачных действий прямой (и может быть корректным шагом). False: путь непрямой/опосредованный (длиннее прямого). None: путь ещё не построен.

    # properties similar to Edge
    id: str = None
    cfg: 'CFG | None' = None
    constraints: Constraints | None = None
    effects: list[Effects] = field(default_factory=list)

    # exists: bool = None  # True, если `ways_count > 0`. False: пути между этой парой улов нет (никакого).
    # ways_count: int = 0  # число всевозможных нециклических путей по ориентированному графу CFG между указанными точками (0 - нет никакого пути)

    # Эти больше не экспортировать >>
    via_nodes: list[Node] = None  # список id узлов (Node),
    via_edges: list[Edge] = None  # список id ребер (Edge)
    cfg_steps: int = 0  # Число пройденных узлов CFG, без учёта их содержимого = число пройденных рёбер
    # Эти больше не экспортировать ^^

    ast_actions: int = 0  # Число узлов c непустым AST node на пути
    transparent_actions: int = 0  # Число узлов с заданным AST node, которые считаются "прозрачными" для студента в том смысле, что он с ними не взаимодействует (вариант "может нажать, а может и не нажать" пока не рассматривается)
    opaque_actions: int = 0  # Число узлов с заданным AST node, которые считаются "непрозрачными" для студента в том смысле, что он должен обязательно их нажать, чтобы пройти по пути
    conditions: int = 0  # Число узлов с заданным AST node, которые относятся к непустым управляющим условиям и должны обязательно быть нажаты студентом
    frame_changes: int = 0  # Число смен фрейма функции (могут встречаться как в узлах, так и на рёбрах)
    frames_added: int = 0  # Число входов в функцию (любую)
    frames_dropped: int = 0  # Число выходов из функции (любой)

    firstMiddleAction: Node = None  # промежуточный узел CFG первого непрозрачного действия на пути
    firstMiddleCondition: Node = None  # промежуточный узел CFG первого непрозрачного УСЛОВИЯ на пути
    firstMiddleFrameChange: Node = None  # промежуточный узел CFG первой смены фрейма стека на пути

    def __post_init__(self):
        # polyfill id
        if not self.id:
            self.id=idgen.next('path')

        if not self.via_nodes or not self.via_edges:
            # init chains
            self.via_nodes = []
            self.via_edges = []
            assert self.from_
            self.via_nodes.append(self.from_)

    def __hash__(self):
        return hash((
            self.from_.id,
            self.to_.id,
            self.is_direct,
            len(self.via_nodes)))

    def is_loop(self) -> bool:
        """ True, если заканчивается на тот же узел, что и начинается.
        Это допустимо, но дальнейшее наращивание пути-цикла невозможно. """
        return self.from_ == self.to_

    def add_step(self, edge: Edge, target_node: Node) -> bool:
        """ returns False if the step cannot be added (no cycles allowed) """
        # validate args compatibility
        assert edge.dst == target_node.id

        # check connectivity with current chain
        # check if the next edge leaves previous node
        assert edge.src == self.via_nodes[-1].id

        if target_node in self.via_nodes and target_node is not self.from_:
            # Do not allow loops.
            return False

        # Проверка совместимости interruption_mode
        # Получаем конечный interruption_mode текущего пути
        final_mode = self.get_final_interruption_mode()
        
        # Получаем начальный interruption_mode добавляемого ребра
        edge_initial_mode = None
        if edge.constraints and edge.constraints.interruption_mode:
            edge_initial_mode = edge.constraints.interruption_mode or InterruptionType.DEFAULT
        
        # Проверяем совместимость через intersection
        intersection = final_mode.intersection(edge_initial_mode)
        if intersection is None:
            # Типы не пересекаются - шаг нельзя добавить
            return False

        # register new step in chains
        self.via_nodes.append(target_node)
        self.via_edges.append(edge)

        self.via_edges.append(edge)
        if not self.changes_interruption_mode():
            # ограничения применяются только до первой смены прерывания.
            self.add_constraints(edge.constraints)
        self.add_effects(*edge.effects or (), *target_node.effects or ())

        # update all info...
        self.to_ = target_node
        self.cfg_steps = (self.cfg_steps or 0) + 1

        if True: # or target_node.metadata.wrapped_ast is not None:

            # check transparency of this action...
            action = target_node.metadata.abstract_action
            if action:
                self.ast_actions = (self.ast_actions or 0) + 1

                if target_node.is_mandatory():
                    # mandatory action/button
                    self.opaque_actions = (self.opaque_actions or 0) + 1
                    # conditions
                    if target_node.is_condition():
                        self.conditions = (self.conditions or 0) + 1

                else:
                    # no button is associated with this node.
                    self.transparent_actions = (self.transparent_actions or 0) + 1


                # frames
                if action.effects:
                    for effect in action.effects:
                        if effect.call_stack:
                            self.frame_changes = (self.frame_changes or 0) + 1
                            if effect.call_stack == CallStackAction.ADD_FRAME:
                                self.frames_added = (self.frames_added or 0) + 1
                            elif effect.call_stack == CallStackAction.DROP_FRAME:
                                self.frames_dropped = (self.frames_dropped or 0) + 1

        self.renew_first_middle_action()#target_node
        self.update_directness()
        return True

    @staticmethod
    def concatenate_paths(path1: 'PathInfo', path2: 'PathInfo') -> 'PathInfo | None':
        """
        Объединяет два пути: path1.from_ → ... → path1.to_ → path2.from_ → ... → path2.to_
        Возвращает новый PathInfo или None, если соединение невозможно (циклы или несовместимость).
        """
        # Проверяем, что пути можно соединить
        if path1.to_ != path2.from_:
            return None

        if path1.is_loop() or path2.is_loop():
            # Дальнейшее наращивание циклических путей невозможно.
            return None

        # Проверка совместимости interruption_mode
        # Получаем конечный interruption_mode первого пути
        path1_final_mode = path1.get_final_interruption_mode()
        
        # Получаем начальный interruption_mode второго пути
        path2_initial_mode = path2.get_initial_interruption_mode() or InterruptionType.DEFAULT
        
        # Проверяем совместимость через intersection
        intersection = path1_final_mode.intersection(path2_initial_mode)
        if intersection is None:
            # Типы не пересекаются - пути нельзя соединить
            return None

        # Инициализируем via_nodes и via_edges для path1, если они не инициализированы
        if not path1.via_nodes or not path1.via_edges:
            if path1.from_:
                path1_nodes = [path1.from_]
            else:
                return None
            path1_edges = []
        else:
            path1_nodes = path1.via_nodes
            path1_edges = path1.via_edges

        # Инициализируем via_nodes и via_edges для path2, если они не инициализированы
        if not path2.via_nodes or not path2.via_edges:
            if path2.from_:
                path2_nodes = [path2.from_]
            else:
                return None
            path2_edges = []
        else:
            path2_nodes = path2.via_nodes
            path2_edges = path2.via_edges

        # Объединяем узлы: path1_nodes + path2_nodes[1:] (убираем дубликат в точке соединения)
        # path1_nodes заканчивается на path1.to_, path2_nodes начинается с path2.from_
        # Так как path1.to_ == path2.from_, мы убираем дубликат
        combined_nodes = path1_nodes + path2_nodes[1:]
        combined_edges = path1_edges + path2_edges

        # Проверяем на циклы: не должно быть повторяющихся узлов (проверяем по ID)
        node_ids = [node.id for node in combined_nodes]
        new_is_loop = bool(path1.from_ == path2.to_)
        if len(node_ids) - new_is_loop != len(set(node_ids)):
            # (!) `-`: Последний узел может равняться первому
            return None

        # Создаём новый PathInfo
        new_path = PathInfo(from_=path1.from_, cfg=path1.cfg)
        new_path.to_ = path2.to_
        new_path.via_nodes = combined_nodes
        new_path.via_edges = combined_edges

        new_path.constraints = path1.constraints
        if not path1.changes_interruption_mode():
            # ограничения применяются только до первой смены прерывания.
            new_path.add_constraints(path2.constraints)
            
        new_path.add_effects(*path1.effects, *path2.effects)

        # Суммируем метрики
        new_path.cfg_steps = path1.cfg_steps + path2.cfg_steps
        new_path.ast_actions = path1.ast_actions + path2.ast_actions
        new_path.transparent_actions = path1.transparent_actions + path2.transparent_actions
        # new_path.opaque_actions = path1.opaque_actions + path2.opaque_actions
        # new_path.conditions = path1.conditions + path2.conditions
        new_path.frame_changes = path1.frame_changes + path2.frame_changes
        new_path.frames_added = path1.frames_added + path2.frames_added
        new_path.frames_dropped = path1.frames_dropped + path2.frames_dropped

        # # Умножаем ways_count (предполагая независимость путей)
        # new_path.ways_count = path1.ways_count * path2.ways_count

        # Объединить информацию о первых встретившихся (приоритет левому пути)
        new_path.renew_first_middle_action()
        new_path.update_directness()

        return new_path

    def add_constraints(self, *other_constraints: Constraints):
        """ Взять первое ограничение -- если пустое, то создать стандартное ограничение по умолчанию.
        Для последующих: interruption mode: Добавлять как пересечение к существующему через chain_merge.
        Соглашение о вызове внешним кодом: ограничения не следует добавлять, если путь уже имеет смены режима прерывания, а добавляемые ограничения должны быть так же до смены режима прерывания.
        """
        if not other_constraints:
            return

        if not self.constraints:
            # Если constraints нет, берём первое и объединяем с остальными...
            self.constraints = next(iter(other_constraints), None) or Constraints()
            other_constraints = other_constraints[1:]

        # Объединяем constraints с новыми через chain_merge, по порядку.
        for constraint in other_constraints:
            self.constraints = Constraints.chain_merge(self.constraints, constraint)

    def add_effects(self, *other_effects: Effects):
        """ Добавить непустые эффекты (из последовательных узлов/рёбер) """
        for effect in other_effects:
            if effect:
                if not self.effects or not (merged := Effects.merge(self.effects[-1], effect)):
                    self.effects.append(effect)
                else:
                    self.effects[-1] = merged

    def get_initial_interruption_mode(self) -> 'InterruptionType | None':
        """Получить начальный interruption_mode пути.
        
        Возвращает constraint первого ребра/перехода пути.
        Если constraints отсутствует или interruption_mode не задан, возвращает None
        (что эквивалентно NO_INTERRUPTION).
        
        Returns:
            Начальный interruption_mode из constraints пути, или None
        """
        if self.constraints and self.constraints.interruption_mode:
            return self.constraints.interruption_mode
        return None

    def get_final_interruption_mode(self) -> 'InterruptionType':
        """Вычислить конечный interruption_mode пути.
        
        Вычисляет конечное состояние прерывания после прохождения пути,
        учитывая все эффекты interruption_start и interruption_stop.
        
        Алгоритм:
        1. Начинает с начального interruption_mode (или NO_INTERRUPTION, если не задан)
        2. Проходит по всем эффектам пути в порядке их добавления
        3. Для каждого эффекта:
           - Если есть interruption_start и он не равен NO_INTERRUPTION, заменяет текущее состояние
           - Если есть interruption_stop и он покрывает текущее состояние, устанавливает NO_INTERRUPTION
        
        Returns:
            Конечное состояние прерывания после прохождения пути
        """
        # Начинаем с начального interruption_mode
        current_mode = self.get_initial_interruption_mode() or InterruptionType.NO_INTERRUPTION
        
        # Проходим по всем эффектам пути в порядке их добавления
        for effect in self.effects:
            if not effect or not effect.changes_interruption_mode():
                continue
            
            # Применяем interruption_start (если задан и не равен NO_INTERRUPTION)
            if effect.interruption_start and effect.interruption_start != InterruptionType.NO_INTERRUPTION:
                current_mode = effect.interruption_start
            
            # Применяем interruption_stop (если задан и покрывает текущее состояние)
            if effect.interruption_stop:
                if effect.interruption_stop.fits(current_mode):
                    current_mode = InterruptionType.NO_INTERRUPTION
        
        return current_mode

    def renew_first_middle_action(self):
        """ Обновить информацию о первом непрозрачном действии, условии и смене фрейма стека на пути. """

        self.opaque_actions = 0
        self.conditions = 0
        for node in self.via_nodes[1:]:  # все, кроме первого
            if node.is_mandatory():
                self.opaque_actions += 1
                if node.is_condition():
                    self.conditions += 1

        for node in self.via_nodes[1:-1]:  # все, кроме первого и последнего
            if node.is_mandatory():
                self.firstMiddleAction = node
                if node.is_condition():
                    self.firstMiddleCondition = node
                    break

        for edge in self.via_edges:  # все.
            if edge.effects:
                for effect in edge.effects:
                    if effect.call_stack in (CallStackAction.ADD_FRAME, CallStackAction.DROP_FRAME):
                        self.firstMiddleFrameChange = self.cfg.nodes[edge.dst]
                        break

    def update_directness(self, target_node: Node | None = None):
        """Обновить статус прямоты/опосредованности пути.

        Если передан node, используется инкрементальная логика.
        В противном случае значение вычисляется по накопленным метрикам.
        """
        # start_node = self.via_nodes[0] if self.via_nodes else self.from_
        # if not start_node or not start_node.is_mandatory():
        #     # Стартовый узел должен быть непрозрачным для любого определённого состояния.
        #     self.is_direct = None
        #     return

        if target_node is not None:
            if target_node.is_mandatory():
                if self.is_direct is None:
                    self.is_direct = True
                elif self.is_direct is True:
                    self.is_direct = False
            return

        opaque_count = self.opaque_actions or 0
        begin_is_mandatory = self.via_nodes[0].is_mandatory()
        end_is_mandatory = self.via_nodes[-1].is_mandatory()
        if opaque_count == 1 and len(self.via_nodes) >= 2 and begin_is_mandatory and end_is_mandatory:
            self.is_direct = True
        elif opaque_count == 0 + end_is_mandatory and (begin_is_mandatory + end_is_mandatory <= 1):
            self.is_direct = None
        else:
            self.is_direct = False


@deprecated("Use determine_all_paths_between_opaque_nodes instead")
def determine_all_paths_through(cfg: CFG, from_: str = None, to_: str = None) -> list[PathInfo]:
    """ 
    Определяет все возможные пути между всеми парами значимых узлов CFG (т.е. узлов, которые ссылаются на непустые AST node).
    При этом пути могут быть циклическими, т.е. начинаться и заканчиваться на одном и том же узле.
    Каждый путь представляет собой список узлов и рёбер, которые проходятся по кратчайшему пути между парой узлов.
    Возвращает список всех путей.

    Реализовано поиском в ширину. После нахождения всех путей выбирать кратчайший, сохранять его и записывать в него число путей.
    Можно применять найденные более короткие пути для нахождения более длинных путей.
    """
    if not from_:
        from_ = cfg.begin_node.id
    if not to_:
        to_ = cfg.end_node.id

    from_node = cfg.nodes[from_]
    to_node = cfg.nodes[to_]

    wavefront = [
        PathInfo(from_=from_node, cfg=cfg)
    ]
    completed_paths: list[PathInfo] = []

    while wavefront:
        next_wavefront = []
        for path in wavefront:
            # Получаем последний узел в пути
            last = path.via_nodes[-1] if path.via_nodes else from_node

            # Расширяем путь всеми исходящими рёбрами
            for edge in cfg.edges_from_node(last):
                next_node = cfg.nodes[edge.dst]

                # Создаём копию пути для расширения
                new_path = copy.deepcopy(path)

                # Пытаемся добавить шаг (вернёт False, если будет цикл)
                if not new_path.add_step(edge, next_node):
                    continue  # цикл обнаружен, пропускаем

                if next_node is to_node:
                    # Достигли целевого узла - добавляем в завершённые пути
                    completed_paths.append(new_path)
                    # продолжаем поиск других путей, не останавливаемся
                else:
                    # Продолжаем поиск с этого пути
                    next_wavefront.append(new_path)

        wavefront = next_wavefront

    # Подсчитываем количество всех найденных путей
    # ways = len(completed_paths)

    # Выбираем кратчайший путь
    if completed_paths:
        shortest = min(completed_paths, key=lambda p: p.opaque_actions)
        # shortest.ways_count = ways
        return [shortest]
    else:
        # Путь не найден
        return []
        # result = PathInfo(from_=from_node, to_=to_node, cfg=cfg)
        # # result.ways_count = 0
        # return [result]


def find_opaque_nodes(cfg: CFG) -> list[Node]:
    """Находит все узлы CFG с AppearanceType.MANDATORY (непрозрачные узлы)."""
    opaque_nodes = []
    for node in cfg.nodes.values():
        if node.is_mandatory():
            opaque_nodes.append(node)
    return opaque_nodes


def determine_all_paths_between_opaque_nodes(cfg: CFG) -> list[PathInfo]:
    """
    Определяет все возможные пути между всеми парами непрозрачных узлов (с AppearanceType.MANDATORY).
    Использует инкрементный подход: сначала находит все пути длины 1, затем итеративно строит
    более длинные пути через сложение уже найденных.
    Возвращает список всех найденных путей, отсортированный по длине (от коротких к длинным).
    """

    # Кэш всех найденных путей: (from_node_id, to_node_id) -> list[PathInfo]
    paths_cache: dict[tuple[str, str], list[PathInfo]] = defaultdict(list)

    # Lookup-словарь для получения "веера" продолжения 
    paths_from_node: dict[str, list[PathInfo]] = defaultdict(list)

    # Функция для добавления пути в кэш
    def add_path_to_cache(path: PathInfo) -> bool:
        """Добавляет путь в кэш. Возвращает True, если путь был добавлен (новый)."""
        if path.from_ is None or path.to_ is None:
            return False
        key = (path.from_.id, path.to_.id)
        # if key not in paths_cache:
        #     paths_cache[key] = []

        # Проверяем, нет ли уже такого пути (сравниваем по via_nodes)
        # Для простоты проверяем только наличие пути с такой же последовательностью узлов
        existing = False
        if path.via_nodes:
            path_signature = hash(path)
            # path_signature = tuple(node.id for node in path.via_nodes)
            for existing_path in paths_cache[key]:
                if existing_path.via_nodes:
                    existing_signature = hash(existing_path)
                    # existing_signature = tuple(node.id for node in existing_path.via_nodes)
                    if path_signature == existing_signature:
                        existing = True
                        break

        if not existing:
            paths_cache[key].append(path)
            paths_from_node[path.from_.id].append(path)
            return True
        return False

    # Инициализация: находим все пути длины 1 (прямые рёбра)
    for edge in cfg.edges:
        from_node = cfg.nodes[edge.src]
        to_node = cfg.nodes[edge.dst]

        # Создаём путь длины 1
        path = PathInfo(from_=from_node, cfg=cfg)
        if path.add_step(edge, to_node):
            # path.ways_count = 1  # Единственный путь через ребро
            add_path_to_cache(path)


    def chain_paths(
            source__is_direct: list[bool | None],
            target__is_direct: list[bool],
            length_limit = None,
            END_priority = False,
            algorithm_end: Node = cfg.end_node
        ) -> None:
        """ Собрать пути, комбинируя более короткие пути
        length_limit: максимальная длина цепочки, из которой может быть составлен целевой путь (None = не ограничено)
        END_priority: если True, то пути, заканчивающаяся концом алгоритма (`algorithm_end`), не подпадают под ограничение длины.
        """
        while True:
            new_paths_found = 0
            
            # Получаем все пути с source__is_direct
            source_paths = []
            for paths_list in paths_cache.values():
                for path in paths_list:
                    if path.is_direct in source__is_direct:
                        source_paths.append(path)
            
            # Для каждого исходного пути ищем пути, которые можно к нему присоединить
            for path1 in source_paths:
                if path1.to_ is None:
                    continue
                
                # Используем paths_from_node для эффективного поиска продолжений
                continuation_paths = paths_from_node.get(path1.to_.id, [])
                
                for path2 in continuation_paths:
                    # Проверяем, что path2 имеет нужный source__is_direct
                    if path2.is_direct not in source__is_direct:
                        continue
                    
                    # Пробуем объединить пути
                    combined = PathInfo.concatenate_paths(path1, path2)
                    if combined is None:
                        continue
                    
                    # Проверяем, что результат имеет нужный target__is_direct
                    if combined.is_direct not in target__is_direct:
                        continue
                    
                    # Проверяем ограничение по длине
                    if length_limit is not None:
                        # Если END_priority=True и путь заканчивается на algorithm_end, пропускаем проверку
                        if not (END_priority and combined.to_ == algorithm_end):
                            # Подсчитываем длину цепочки (количество opaque_actions)
                            chain_length = combined.opaque_actions or 0
                            if chain_length > length_limit:
                                continue
                    
                    # Добавляем путь в кэш
                    if add_path_to_cache(combined):
                        new_paths_found += 1
            
            # Если новая итерация не дала новых путей, останавливаемся
            if new_paths_found == 0:
                break



    # Итеративное построение более длинных путей, останавливаясь на "непрозрачных" узлах (которые "с кнопками").
    # 1. Сначала прямые из неполных (None -> True)
    chain_paths([None], [None, True])
    # 2. Затем непрямые(опосредованные) из прямых (True -> False)
    # Ограничиваем длину цепочки до 4, но пути к концу алгоритма имеют приоритет
    chain_paths([True, False], [False], length_limit=4, END_priority=True)

    # Фильтруем результат: оставляем только пути между opaque узлами
    result_paths: list[PathInfo] = []

    for paths in paths_cache.values():
        for path in paths:
            if path.is_direct is not None:  # direct or indirect, but not incomplete
                result_paths.append(path)

    # Дедупликация: для одинаковых (from_, to_, constraints) оставляем кратчайший путь
    def constraints_key(constraints: Constraints | None) -> tuple:
        """Создаёт ключ для сравнения constraints."""
        if constraints is None:
            return (None, None)
        return (
            constraints.condition_value.value if constraints.condition_value else None,
            constraints.interruption_mode.value if constraints.interruption_mode else None,
        )

    # Группируем пути по (from_, to_, constraints, is_direct)
    paths_by_key: dict[tuple[str, str, tuple, bool | None], list[PathInfo]] = {}
    for path in result_paths:
        if path.from_ is None or path.to_ is None:
            continue
        key = (
            path.from_.id,
            path.to_.id,
            constraints_key(path.constraints),
            path.is_direct,
        )
        if key not in paths_by_key:
            paths_by_key[key] = []
        paths_by_key[key].append(path)

    # Для каждой группы оставляем кратчайший путь (по opaque_actions)
    deduplicated_paths: list[PathInfo] = []
    for paths_group in paths_by_key.values():
        shortest = min(paths_group, key=lambda p: p.opaque_actions)
        deduplicated_paths.append(shortest)

    # Сортируем по длине пути (от коротких к длинным)
    deduplicated_paths.sort(key=lambda p: p.opaque_actions)
    result_paths = deduplicated_paths

    # После вычисления всех путей обновляем информацию в узлах
    for node in cfg.nodes.values():
        node.clear_direct_paths()

    for path in result_paths:
        if path.is_direct is not True:
            # skip incomplete/indirect paths
            continue
        if path.from_:
            path.from_.register_direct_path(path)
        if path.to_:
            path.to_.register_direct_path(path, incoming=True)

    return result_paths



