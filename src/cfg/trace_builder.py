"""
Модуль для генерации трасс выполнения программы из CFG.

Основные возможности:
- Генерация нескольких трасс для одного CFG с различными сценариями выполнения
- Детерминированное или случайное задание значений управляющих условий
- Защита от бесконечных циклов через ограничение количества посещений узлов
- Автоматическое переключение веток при приближении к лимиту посещений
- Формирование цепочки выполнения через связь directly_before_of

Основные компоненты:
- TraceScenarioConfig: конфигурация сценария выполнения (значения условий, лимиты)
- generate_trace_variants: генерация нескольких трасс для разных сценариев
- _ConditionDecisionProvider: управление последовательностью значений условий
- TraceAct: акт трассы с установленными связями directly_before_of
"""

import random
import sys
import warnings
from collections import defaultdict, deque
from collections.abc import Generator, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from src.cfg.abstractions import InterruptionType, OptionalBoolValue, Effects
from src.cfg.cfg import CFG, Edge, Node, NodeKind, TraceAct
from src.code_renderer import ButtonType


@dataclass
class UserInteraction:
    ast_node_id: int
    button_type: ButtonType
    atom: bool


@warnings.deprecated("Use trace scenarios and building using cfg instead")
def all_interactions(lines_data: list[dict[str, list]]) -> Generator[UserInteraction]:
    for line in lines_data:
        for button in line.get("buttons", []):
            yield UserInteraction(
                ast_node_id=button["node_id"], button_type=button["type"], atom=button["atom"]
            )


@dataclass
class ConditionDecisionSchedule:
    """Расписание значений для управляющего условия.

    Определяет последовательность значений (True/False), которые условие будет принимать
    при каждом посещении узла. Используется для детерминированного построения трассы.

    Attributes:
        values: Список значений условия в порядке их использования. Каждое значение
                используется один раз при соответствующем посещении узла.
        fallback: Значение по умолчанию, если список values исчерпан. Если None,
                  используется случайное значение или значение из конфигурации.
    """

    values: list[bool] = field(default_factory=list)
    fallback: bool | None = None


@dataclass
class TraceScenarioConfig:
    """Настройки генерации трассы для конкретного сценария выполнения программы.

    Позволяет задать детерминированный или случайный сценарий выполнения программы,
    определяя значения управляющих условий (if, while, for) на каждом шаге трассировки.

    Основные возможности:
    - Задать последовательность значений для конкретных условий (по AST node id)
    - Ограничить количество посещений каждого узла (защита от бесконечных циклов)
    - Автоматически переключать ветку при приближении к лимиту посещений
    - Генерировать случайные значения для условий, не заданных явно

    Attributes:
        name: Имя сценария (используется для идентификации при экспорте)
        condition_sequences: Словарь {ast_node_id: schedule}, где schedule - это либо
                            ConditionDecisionSchedule, либо список bool значений.
                            Определяет последовательность значений для каждого условия.
        max_visits_per_node: Максимальное количество посещений одного узла (по умолчанию 3-4).
                            При достижении лимита выполнение останавливается или переключается
                            на альтернативную ветку (если это условие).
        max_steps: Максимальное количество шагов в трассе (защита от зацикливания)
        randomize_missing_conditions: Если True, для условий без заданной последовательности
                                     генерируются случайные значения. Иначе используется False.
        seed: Seed для генератора случайных чисел (для воспроизводимости)

    Example:
        # Сценарий с детерминированными значениями условий
        config = TraceScenarioConfig(
            name="true_then_false",
            condition_sequences={
                42: [True, False],  # Условие с id=42: сначала True, потом False
            },
            max_visits_per_node=3
        )
    """

    name: str = "default"
    condition_sequences: Mapping[int, ConditionDecisionSchedule | Sequence[bool]] = field(
        default_factory=dict
    )
    max_visits_per_node: int = 4
    max_steps: int = 500
    randomize_missing_conditions: bool = True
    seed: int | None = None

    def __post_init__(self):
        normalized: Mapping[int, ConditionDecisionSchedule] = {}
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
    condition_value: OptionalBoolValue | None = None
    incomplete_interruption: InterruptionType | None = None


@dataclass
class TraceGenerationResult:
    """Результат генерации трассы для одного сценария.

    Attributes:
        scenario: Конфигурация сценария, использованная для генерации
        trace_acts: Список актов трассы в порядке выполнения с установленными связями
        terminated_by_limit: Флаг, указывающий, было ли выполнение остановлено из-за
                            превышения лимита посещений узла (защита от бесконечных циклов)
    """

    scenario: TraceScenarioConfig
    trace_acts: list[TraceAct]
    terminated_by_limit: bool


class _ConditionDecisionProvider:
    """Провайдер решений для управляющих условий при построении трассы.

    Управляет последовательностью значений условий, извлекая следующее значение
    из заданной последовательности или генерируя случайное/fallback значение.
    Ведёт историю принятых решений для каждого узла.

    Логика работы:
    1. При первом запросе значения для узла извлекается первое значение из sequences
    2. При последующих запросах - следующие значения по порядку
    3. Если последовательность исчерпана, используется fallback или случайное значение
    4. Все принятые решения сохраняются в истории для анализа
    """

    def __init__(self, cfg: CFG, scenario: TraceScenarioConfig):
        self._scenario = scenario
        self._random = random.Random(scenario.seed)
        self._node_sequences: dict[str, deque[OptionalBoolValue]] = {}
        self._history: dict[str, list[OptionalBoolValue]] = defaultdict(list)
        for node in cfg.nodes.values():
            ast_id = _get_ast_id(node)
            if ast_id is None:
                continue
            schedule = scenario.condition_sequences.get(ast_id)
            if schedule and isinstance(schedule, ConditionDecisionSchedule):
                # Преобразуем bool значения в OptionalBoolValue
                converted_values = [
                    OptionalBoolValue.true
                    if v is True
                    else OptionalBoolValue.false
                    if v is False
                    else v
                    for v in schedule.values
                ]
                self._node_sequences[node.id] = deque(converted_values)

    def request(self, node: Node) -> OptionalBoolValue | None:
        seq = self._node_sequences.get(node.id)
        if seq and seq:
            return seq.popleft()
        ast_id = _get_ast_id(node)
        schedule = self._scenario.condition_sequences.get(ast_id) if ast_id is not None else None
        if (
            schedule
            and isinstance(schedule, ConditionDecisionSchedule)
            and schedule.fallback is not None
        ):
            # Преобразуем bool в OptionalBoolValue
            fallback = schedule.fallback
            if fallback is True:
                return OptionalBoolValue.true
            elif fallback is False:
                return OptionalBoolValue.false
            return fallback
        if self._scenario.randomize_missing_conditions:
            return self._random.choice([OptionalBoolValue.true, OptionalBoolValue.false])
        return OptionalBoolValue.false

    def commit(self, node: Node, value: OptionalBoolValue | None):
        if value is None:
            return
        self._history[node.id].append(value)

    def history_for(self, node: Node) -> list[OptionalBoolValue]:
        return self._history.get(node.id, [])


def generate_trace_variants(
    cfg: CFG, scenarios: Iterable[TraceScenarioConfig] | None
) -> list[TraceGenerationResult]:
    """Генерирует набор трасс для одного CFG с различными сценариями выполнения.

    Для каждого сценария создаётся отдельная трасса, отличающаяся значениями
    управляющих условий. Это позволяет создать несколько вариантов выполнения
    одной и той же программы (например, разные пути в if-else, разное количество
    итераций циклов).

    Args:
        cfg: Граф потока управления, для которого генерируются трассы
        scenarios: Список конфигураций сценариев. Если None, используется
                  один сценарий по умолчанию.

    Returns:
        Список результатов генерации, каждый содержит трассу для соответствующего сценария

    Example:
        scenarios = [
            TraceScenarioConfig(name="all_true", condition_sequences={1: [True]}),
            TraceScenarioConfig(name="all_false", condition_sequences={1: [False]}),
        ]
        results = generate_trace_variants(cfg, scenarios)
        # results[0] - трасса для сценария "all_true"
        # results[1] - трасса для сценария "all_false"
    """
    scenario_list = list(scenarios) if scenarios else [TraceScenarioConfig()]
    results: list[TraceGenerationResult] = []
    for scenario in scenario_list:
        result = _generate_trace_for_scenario(cfg, scenario)
        if result.terminated_by_limit:
            # Skip incomplete traces!
            print(f'WARN: Trace construction for scenario `{scenario.name}` was terminated by limit!', file=sys.stderr)
            continue
        results.append(result)
    return results


def _generate_trace_for_scenario(cfg: CFG, scenario: TraceScenarioConfig) -> TraceGenerationResult:
    """Генерирует одну трассу для заданного сценария.

    Алгоритм построения трассы:
    1. Начинаем с BEGIN-узла CFG
    2. Для каждого узла:
       - Если узел обязательный (is_mandatory), добавляем его в трассу
       - Если узел - условие, запрашиваем значение из провайдера
       - Выбираем следующее ребро на основе значения условия и лимитов посещений
       - Если достигнут лимит посещений узла, переключаемся на альтернативную ветку
    3. Продолжаем до достижения END узла или превышения лимитов

    Особенности:
    - Учитывается ограничение на количество посещений узла (max_visits_per_node)
    - При приближении к лимиту условие автоматически переключается на противоположное
      значение, чтобы выйти из цикла (например, True -> False для выхода из while)
    - Для каждого обязательного узла сохраняется значение условия (если это условие)
    - Формируется цепочка актов через поле directly_before_of

    Args:
        cfg: Граф потока управления
        scenario: Конфигурация сценария выполнения

    Returns:
        Результат генерации с трассой и флагом завершения по лимиту
    """
    provider = _ConditionDecisionProvider(cfg, scenario)
    visit_counts: dict[str, int] = defaultdict(int)
    # Стек вызовов функций: содержит ast_id узлов-вызовов (обёрток func_call)
    # Используется только для выбора корректного ребра возврата из общего CFG тела функции.
    entered_stack: list[int] = []  # ids of ASTNodes
    visited_nodes: list[VisitedNode] = []
    current = cfg.begin_node
    steps = 0
    terminated_by_limit = False
    interruption_state = InterruptionType.NO_INTERRUPTION

    while current and steps < scenario.max_steps:
        steps += 1
        visit_counts[current.id] += 1
        if visit_counts[current.id] > scenario.max_visits_per_node:
            terminated_by_limit = True
            break

        record_index = len(visited_nodes)
        if current.is_mandatory():
            visited_nodes.append(VisitedNode(node=current))

        # update stack according to node type...
        if current.kind == NodeKind.BEGIN:
            entered_stack.append(current.get_ast_id())
        elif current.kind == NodeKind.END:
            ast_id = current.get_ast_id()
            leaving_ast_id = entered_stack.pop()
            assert leaving_ast_id == ast_id
        # ATOM: no change.

        if current == cfg.end_node:
            break

        # Применяем эффекты interruption_start из текущего узла
        previous_interruption_state = interruption_state
        interruption_state = _apply_effects(current.effects, interruption_state)
        
        ###
        # print(entered_stack, interruption_state, current.effects)
        ###

        # Если прерывание только что началось, нужно найти первую кнопку и пометить её
        # if (previous_interruption_state == InterruptionType.NO_INTERRUPTION and
            # interruption_state != InterruptionType.NO_INTERRUPTION):
            # # Прерывание только что началось - находим первую кнопку от текущего узла
            # first_button_node = _find_first_mandatory_node_from(cfg, current)
            # if first_button_node and first_button_node != current:
            #     # Если текущий узел не является кнопкой, добавляем путь до первой кнопки
            #     # и помечаем её незавершённым прерыванием
            #     if current.is_mandatory() and record_index < len(visited_nodes):
            #         # Текущий узел уже добавлен - помечаем его незавершённым прерыванием
            #         visited_nodes[record_index].incomplete_interruption = interruption_state
            #     else:
            #         # Нужно добавить первую кнопку с пометкой незавершённого прерывания
            #         # Переходим к первой кнопке напрямую
            #         current = first_button_node
            #         if current.is_mandatory():
            #             visited_nodes.append(VisitedNode(node=current, incomplete_interruption=interruption_state))
            #         continue

        # Верхушка стека вызовов на момент выбора следующего узла
        current_context_ast_id = entered_stack[-1] if entered_stack else None

        next_node, condition_value, chosen_edge = _choose_next_node(
            cfg,
            current,
            visit_counts[current.id],
            scenario,
            provider,
            interruption_state,
            current_context_ast_id,
        )

        # Применяем эффекты выбранного ребра:
        # 1) обновляем стек вызовов по call_stack
        # 2) обновляем состояние прерываний через interruption_stop
        if chosen_edge:
            # if chosen_edge.effects:
                # for effect in chosen_edge.effects:
                #     if effect.call_stack == CallStackAction.ADD_FRAME:
                #         # В стек кладём ast_id узла-вызова (обёртка func_call),
                #         # которым является текущий CFG-узел.
                #         ast_id = _get_ast_id(current)
                #         if ast_id is not None:
                #             entered_stack.append(ast_id)
                #     elif effect.call_stack == CallStackAction.DROP_FRAME and entered_stack:
                #         # Выход из функции: снимаем верхний кадр стека
                #         entered_stack.pop()

            interruption_state = _apply_effects(chosen_edge.effects, interruption_state)

        if current.is_mandatory() and record_index < len(visited_nodes):
            visited_nodes[record_index].condition_value = (
                condition_value if current.is_condition() else None
            )

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
    interruption_state: InterruptionType,
    current_context_ast_id: int | None,
) -> tuple[Node | None, OptionalBoolValue | None, Edge | None]:
    """Выбирает следующий узел для перехода из текущего узла.

    Логика выбора:
    - Для узлов-условий: запрашивает значение из провайдера и выбирает соответствующее ребро
    - Для обычных узлов: выбирает первое доступное ребро
    - Фильтрует рёбра по interruption_mode в constraints с учётом текущего состояния прерывания

    Важная особенность - защита от бесконечных циклов:
    Если узел посещён (max_visits_per_node - 1) раз и текущее решение True
    (что может привести к циклу), автоматически переключается на False,
    чтобы выйти из цикла до превышения лимита.

    Args:
        cfg: Граф потока управления
        node: Текущий узел
        visit_count: Количество уже выполненных посещений этого узла
        scenario: Конфигурация сценария
        provider: Провайдер решений для условий
        interruption_state: Текущее состояние прерывания
        current_context_ast_id: ast_id верхнего кадра стека вызовов (обёртки func_call)

    Returns:
        Кортеж (следующий_узел, значение_условия, выбранное_ребро).
        Значение условия: None для не-условий.
    """
    edges = cfg.edges_from_node(node)
    if not edges:
        return None, None, None

    # Фильтруем рёбра по состоянию прерывания
    available_edges = _filter_edges_by_interruption(edges, interruption_state, current_context_ast_id, cfg)

    # Если после фильтрации не осталось доступных рёбер, возвращаем None
    if not available_edges:
        return None, None, None

    if node.is_condition():
        decision = provider.request(node)
        chosen_edge = _edge_for_condition(available_edges, decision)

        # Защита от бесконечных циклов: если приближаемся к лимиту и решение True,
        # переключаемся на False, чтобы выйти из цикла
        if visit_count >= scenario.max_visits_per_node - 1 and decision == OptionalBoolValue.true:
            alternate_edge = _edge_for_condition(available_edges, OptionalBoolValue.false)
            if alternate_edge:
                decision = OptionalBoolValue.false
                chosen_edge = alternate_edge

        if chosen_edge is None:
            # fallback to any available edge
            chosen_edge = available_edges[0]

        provider.commit(node, decision)
        return cfg.nodes.get(chosen_edge.dst), decision, chosen_edge

    # Неусловные узлы: обычно выбираем первое доступное ребро.
    # Специальный случай — общий END тела функции, из которого есть несколько
    # выходов к разным обёрткам вызовов одной и той же функции (в т.ч. рекурсивных).
    # В этом случае используем вершину стека вызовов, чтобы выбрать корректное ребро.

    # Попытка стек-ориентированного выбора для конца функции
    # if node.kind == NodeKind.END and current_context_ast_id is not None:
    #     # Среди доступных рёбер ищем те, которые сбрасывают кадр стека (DROP_FRAME).
    #     # Такие рёбра соответствуют возвратам из функции к обёрткам вызовов.
    #     candidates_with_drop: list[Edge] = []
    #     for edge in available_edges:
    #         if not edge.effects:
    #             continue
    #         for effect in edge.effects:
    #             if effect.call_stack == CallStackAction.DROP_FRAME:
    #                 candidates_with_drop.append(edge)
    #                 break
    #
    #     if candidates_with_drop:
    #         # Сначала ищем ребро, ведущее к обёртке вызова с ast_id, совпадающим
    #         # с верхушкой стека вызовов. Это обеспечивает корректный возврат по стеку.
    #         for edge in candidates_with_drop:
    #             dst_node = cfg.nodes.get(edge.dst)
    #             if not dst_node:
    #                 continue
    #             dst_ast_id = _get_ast_id(dst_node)
    #             if dst_ast_id is not None and dst_ast_id == current_context_ast_id:
    #                 return dst_node, None, edge
    #
    #         # Если точного совпадения по ast_id нет (деградация для нестандартных случаев),
    #         # используем первое ребро с DROP_FRAME, чтобы сохранить прежнюю семантику.
    #         fallback_edge = candidates_with_drop[0]
    #         return cfg.nodes.get(fallback_edge.dst), None, fallback_edge

    # Обычный случай: берём первое доступное ребро
    chosen = available_edges[0]
    return cfg.nodes.get(chosen.dst), None, chosen


def _edge_for_condition(edges: list, decision: OptionalBoolValue | None):
    """Выбирает ребро CFG, соответствующее значению условия.

    Ищет ребро, у которого constraint.condition_value совпадает с decision.
    Если такого ребра нет, возвращает первое ребро с constraint = ANY или NO_VALUE.

    Args:
        edges: Список рёбер из текущего узла
        decision: Значение условия (OptionalBoolValue/None)

    Returns:
        Ребро, соответствующее условию, или None, если не найдено
    """
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
    """Преобразует список посещённых узлов в список актов трассы.

    Создаёт TraceAct для каждого обязательного узла, устанавливая:
    - Значение условия (condition_value) для узлов-условий
    - Связь corresponding_end для BEGIN/END пар (начало и конец блока)
    - Связь directly_before_of для формирования цепочки выполнения

    Связь directly_before_of устанавливается так, что каждый акт (кроме последнего)
    ссылается на следующий акт в трассе, формируя последовательность выполнения программы.

    Args:
        visited: Список посещённых узлов с сохранёнными значениями условий

    Returns:
        Список актов трассы с установленными связями
    """
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
                is_known_correct=False,
                condition_value=record.condition_value,
                button_type=_infer_button_type(node),
                incomplete_interruption=record.incomplete_interruption,
            )
        )

    # Устанавливаем связи corresponding_end для BEGIN/END узлов
    # (связывает начало и конец одного и того же блока/конструкции)
    for trace_act in trace:
        if trace_act.cfg_node.kind not in {NodeKind.BEGIN, NodeKind.END}:
            continue
        opposite = NodeKind.END if trace_act.cfg_node.kind == NodeKind.BEGIN else NodeKind.BEGIN
        for candidate in trace:
            if (
                candidate.cfg_node.kind == opposite
                and candidate.wrapped_ast
                and trace_act.wrapped_ast
                and candidate.wrapped_ast.ast_node.get("id")
                == trace_act.wrapped_ast.ast_node.get("id")
            ):
                trace_act.corresponding_end = candidate
                break

    # Устанавливаем связи directly_before_of (цепочка последовательности выполнения)
    # Каждый акт ссылается на следующий акт в трассе
    for i in range(len(trace) - 1):
        trace[i].directly_before_of = trace[i + 1]

    if trace:
        # Для самого первого акта трассы (начало алгоритма) задаём флаг для удобства поиска в дальнейшем.
        # Этот акт не имеет кнопки в UI и неявно уже выполнен.
        trace[0].is_known_correct = True

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
    """Извлекает ID AST-узла из CFG-узла.

    Args:
        node: CFG-узел с метаданными

    Returns:
        ID AST-узла или None, если не найден
    """
    if node.metadata.wrapped_ast and isinstance(node.metadata.wrapped_ast.ast_node, dict):
        return node.metadata.wrapped_ast.ast_node.get("id")
    return None


def _apply_effects(effects: list[Effects], current_state: InterruptionType) -> InterruptionType:
    """Применяет эффекты interruption_start из узла.

    Проверяет все эффекты узла и применяет interruption_start, если он задан.
    Если interruption_start не равен NO_INTERRUPTION, он заменяет текущее состояние.

    Args:
        effects: список эффектов
        current_state: Текущее состояние прерывания

    Returns:
        Новое состояние прерывания после применения эффектов узла
    """
    if not effects:
        return current_state

    for effect in effects:
        if effect.interruption_start and effect.interruption_start != InterruptionType.NO_INTERRUPTION:
            return effect.interruption_start

        if effect.interruption_stop:
            # Если interruption_stop покрывает текущее состояние, сбрасываем его
            if effect.interruption_stop.fits(current_state):
                return InterruptionType.NO_INTERRUPTION

    return current_state


# def _apply_edge_effects(edge: Edge, current_state: InterruptionType) -> InterruptionType:
#     """Применяет эффекты interruption_stop из ребра.
#
#     Проверяет все эффекты ребра и применяет interruption_stop, если он задан.
#     Если interruption_stop соответствует текущему состоянию прерывания,
#     состояние сбрасывается в NO_INTERRUPTION.
#
#     Args:
#         edge: Ребро CFG с эффектами
#         current_state: Текущее состояние прерывания
#
#     Returns:
#         Новое состояние прерывания после применения эффектов ребра
#     """
#     if not edge.effects:
#         return current_state
#
#     for effect in edge.effects:
#         if effect.interruption_stop:
#             # Если interruption_stop покрывает текущее состояние, сбрасываем его
#             if effect.interruption_stop.fits(current_state):
#                 return InterruptionType.NO_INTERRUPTION
#
#     return current_state


def _filter_edges_by_interruption(
    edges: list[Edge], interruption_state: InterruptionType, current_context_ast_id: int | None, cfg: CFG,
) -> list[Edge]:
    """Фильтрует рёбра по interruption_mode в constraints.

    Логика фильтрации:
    - interruption_mode = ANY → ребро доступно всегда
    - interruption_mode = NO_INTERRUPTION → доступно только при состоянии NO_INTERRUPTION
    - interruption_mode = конкретное_прерывание → доступно только при соответствующем состоянии
    - interruption_mode = None (отсутствие constraints) → подразумевает NO_INTERRUPTION,
      доступно только при состоянии NO_INTERRUPTION

    Когда текущее состояние = NO_INTERRUPTION:
    Доступны только рёбра с interruption_mode = ANY, NO_INTERRUPTION или None.

    Args:
        edges: Список рёбер для фильтрации
        interruption_state: Текущее состояние прерывания

    Returns:
        Отфильтрованный список рёбер, доступных при текущем состоянии прерывания
    """
    filtered = []

    for edge in edges:
        # # Если у ребра нет constraints, interruption_mode подразумевает NO_INTERRUPTION
        if edge.constraints is None:
            interruption_constraint = None
        else:
            interruption_constraint = edge.constraints.interruption_mode

        if not interruption_constraint:
            interruption_constraint = InterruptionType.DEFAULT  # i.e. NO_INTERRUPTION

        # Проверяем, покрывает ли interruption_constraint текущее состояние прерывания
        # Ребро доступно, если требуемый режим покрывает текущее состояние
        if not interruption_constraint.fits(interruption_state):
            # не покрывает!
            continue

        # Завершиться должно то, что началось ранее.
        if current_context_ast_id is not None:
            target_node = cfg.nodes.get(edge.dst)
            if target_node and target_node.kind == NodeKind.END and target_node.get_ast_id() != current_context_ast_id:
                # возврат не туда!
                continue

        filtered.append(edge)

    return filtered


@warnings.deprecated("Use trace scenarios and building using cfg instead")
def build_trace_act(cfg: CFG, interaction: UserInteraction) -> TraceAct | None:
    raise DeprecationWarning()
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
                raise ValueError(f"Unknown button type: {interaction.button_type}")
                kind = NodeKind.ANY
        if node.kind == kind or (kind != NodeKind.END and node.kind != NodeKind.END):
            return TraceAct(
                wrapped_ast=node.metadata.wrapped_ast,
                cfg_node=node,
                action_spec=node.metadata.abstract_action,
                corresponding_end=None,
                is_known_correct=False,
                condition_value=None,
                button_type=interaction.button_type,
            )
    print(f"Warning: No matching node found for interaction: {interaction}", file=sys.stderr)
    return None

@warnings.deprecated("Use trace scenarios and building using cfg instead")
def build_trace_for(cfg: CFG, interactions: list[UserInteraction]) -> list[TraceAct]:
    raise DeprecationWarning()
    trace = []
    for interaction in interactions:
        for node in cfg.nodes.values():
            if not node.metadata.wrapped_ast or not isinstance(
                node.metadata.wrapped_ast.ast_node, dict
            ):
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
                trace.append(
                    TraceAct(
                        wrapped_ast=node.metadata.wrapped_ast,
                        cfg_node=node,
                        action_spec=node.metadata.abstract_action,
                        corresponding_end=None,
                        is_known_correct=False,
                        condition_value=None,
                    )
                )
    # Устанавливаем связи corresponding_end для BEGIN/END узлов
    for trace_act in trace:
        if trace_act.cfg_node.kind not in [NodeKind.BEGIN, NodeKind.END]:
            continue
        opposite = NodeKind.END if trace_act.cfg_node.kind == NodeKind.BEGIN else NodeKind.BEGIN
        for potential_end in trace:
            if potential_end.cfg_node.kind == opposite and potential_end.wrapped_ast.ast_node.get(
                "id"
            ) == trace_act.wrapped_ast.ast_node.get("id"):
                trace_act.corresponding_end = potential_end
                break

    # Устанавливаем связи directly_before_of (следующий акт в трассе)
    for i in range(len(trace) - 1):
        trace[i].directly_before_of = trace[i + 1]

    assert len(trace) == len(interactions)
    return trace
