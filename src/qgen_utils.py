import re
import sys
import warnings
from dataclasses import dataclass
from typing import Any

from src.cfg.abstractions import InterruptionType, SituationState, load_constructs
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import CFG, NodeKind, TraceAct
from src.cfg.cfg_builder import CFGBuilder
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.reachability import determine_all_paths_between_opaque_nodes
from src.cfg.trace_builder import (
    TraceScenarioConfig,
    all_interactions,
    build_trace_act,
    generate_trace_variants,
)
from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_dict, to_tokens


@dataclass
class LoqiVariant:
    name: str
    loqi: str
    trace_acts: list[TraceAct]


def find_concepts(mt: dict[str, Any]) -> list[str]:
    return []


def find_skills(mt: dict[str, Any]) -> list[str]:
    return []


def find_tags(mt: dict[str, Any], language: str) -> list[str]:
    return [language]


def build_loqi(ast_json: dict[str, Any], lines: list[dict[str, list[Any]]]):
    constructs = load_constructs("constructs.yml")
    program_root = ASTNodeWrapper(ast_node=ast_json)
    b = CFGBuilder(constructs)
    # Генерируем CFG
    cfg = b.make_cfg_for_ast(program_root)

    if cfg is None:
        return None, None, []

    # Оптимизируем CFG
    cfg.optimize()

    # Экспортируем в LOQI
    exporter = LoqiExporter()

    exporter.add_object(
        situation := SituationState(
            interruption_state=InterruptionType.NO_INTERRUPTION,
        )
    )
    exporter.set_var("STATE", situation)

    trace_acts: list[TraceAct | None] = [
        build_trace_act(cfg, interaction) for interaction in all_interactions(lines)
    ] # все действия трассы для задачи, которые вообще могут понадобиться

    if trace_acts and trace_acts[0]:
        # Для самого первого акта трассы (начало алгоритма) задаём флаг для удобства поиска в дальнейшем.
        # Этот акт не имеет кнопки в UI и неявно уже выполнен.
        trace_acts[0].is_known_correct = True

    for trace_act in trace_acts:
        exporter.add_object(trace_act)

    # Добавляем пути между узлами
    paths = determine_all_paths_between_opaque_nodes(cfg)
    if paths:
        exporter.add_paths(paths)

    return exporter.export_cfg(cfg, None), cfg, trace_acts


def build_loqi_variants(
    ast_json: dict[str, Any],
    trace_configs: list[TraceScenarioConfig] | None,
) -> tuple[list[LoqiVariant], CFG | None]:
    """Генерирует несколько LOQI-описаний для одного CFG с различными трассами выполнения.
    
    Создаёт несколько вариантов экспорта, где CFG и описание алгоритма остаются одинаковыми,
    но трассы выполнения различаются в зависимости от заданных сценариев. Это позволяет
    создать набор вариантов выполнения программы с разными путями ветвления и количеством
    итераций циклов.
    
    Процесс:
    1. Строит CFG из AST
    2. Генерирует трассы для каждого сценария (TraceScenarioConfig)
    3. Для каждой трассы создаёт отдельный LOQI-файл с одинаковым CFG, но разной трассой
    4. Устанавливает связи directlyBeforeOf между актами трассы
    
    Args:
        ast_json: JSON-представление AST программы
        trace_configs: Список конфигураций сценариев трассировки. Если None, используется
                      один сценарий по умолчанию.
    
    Returns:
        Кортеж (список вариантов LOQI, CFG). Каждый вариант содержит:
        - name: имя сценария
        - loqi: текст LOQI-файла
        - trace_acts: список актов трассы с установленными связями
    
    Example:
        configs = [
            TraceScenarioConfig(name="true_branch", condition_sequences={1: [True]}),
            TraceScenarioConfig(name="false_branch", condition_sequences={1: [False]}),
        ]
        variants, cfg = build_loqi_variants(ast_json, configs)
        # variants[0] - LOQI для сценария "true_branch"
        # variants[1] - LOQI для сценария "false_branch"
    """
    raise DeprecationWarning("This function is deprecated. Use alternative methods for generating LOQI variants.")

    constructs = load_constructs("constructs.yml")
    program_root = ASTNodeWrapper(ast_node=ast_json)
    builder = CFGBuilder(constructs)
    cfg = builder.make_cfg_for_ast(program_root)

    if cfg is None:
        return [], None

    cfg.optimize()

    scenarios = trace_configs or [TraceScenarioConfig()]
    trace_results = generate_trace_variants(cfg, scenarios)

    base_paths = determine_all_paths_between_opaque_nodes(cfg)
    variants: list[LoqiVariant] = []

    for result in trace_results:
        exporter = LoqiExporter()
        exporter.add_object(
            situation := SituationState(
                interruption_state=InterruptionType.NO_INTERRUPTION,
            )
        )
        exporter.set_var("STATE", situation)

        # Используем add_trace вместо add_object, чтобы установить связи directlyBeforeOf
        exporter.add_trace(result.trace_acts)

        if base_paths:
            exporter.add_paths(base_paths)

        loqi_text = exporter.export_cfg(cfg, None)
        variants.append(
            LoqiVariant(
                name=result.scenario.name,
                loqi=loqi_text,
                trace_acts=result.trace_acts,
            )
        )

    return variants, cfg


# Символы/диапазоны недопустимые в именах файлов (Windows + управляющие символы)
_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _clean_segment(s: str, max_len: int) -> str:
    # нормализуем пробелы
    s = re.sub(r"\s+", " ", s).strip()
    # удаляем запрещённые символы
    s = _FORBIDDEN_RE.sub("", s)
    # заменим оставшиеся неподходящие символы (если есть) на нижнее подчёркивание,
    # но позволим буквы, цифры, дефис, подчёркивание и точку
    s = re.sub(r"[^A-Za-z0-9\-\._ ]+", "_", s)
    # обрезаем до max_len (предпочтительно не резать слово посередине, но простое срезание достаточно)
    s = s[:max_len]
    # убираем завершающие пробелы и точки (Windows не любит имена, оканчивающиеся точкой/пробелом)
    s = s.rstrip(" .")
    return s


def create_question_name(mt: dict[str, Any], code: str) -> str:
    """
    Возвращает имя из 48-символьной выдержки кода (очищенной от запрещённых символов)
    с добавлением _<unique_hash> в конце (если он есть).
    """
    if not isinstance(code, str):
        code = str(code or "")

    # берем сначала значимую часть: удаляем лидирующие/трейлинг пробелы,
    # затем выбираем первые N символов исходного кода (чтобы выдержка отражала начало)
    N = 48
    excerpt_source = code.strip()
    # если код многострочный, логично взять первую ненулевую строку
    lines = [ln for ln in excerpt_source.splitlines() if ln.strip()]
    if lines:
        base = lines[0]
    else:
        base = excerpt_source

    cleaned = _clean_segment(base, N)
    # если после очистки строка короче N, можно дополнить следующим содержимым (опционально)
    if len(cleaned) < N and len(excerpt_source) > len(base):
        # возьмём продолжение (следующие символы из исходного текста), очистим и доклеим
        rest = "".join(lines[1:]) or excerpt_source[len(base) :]
        if rest:
            rest_clean = _clean_segment(rest, N - len(cleaned))
            cleaned = (cleaned + rest_clean)[:N]

    # подготовим хеш (если есть) и тоже очистим от запрещённых символов
    raw_hash = mt.get("unique_hash") if isinstance(mt, dict) else None
    hash_part = ""
    if raw_hash is not None:
        hash_str = str(raw_hash)
        hash_str = _FORBIDDEN_RE.sub("", hash_str)
        hash_str = re.sub(r"[^A-Za-z0-9\-\._]+", "_", hash_str).strip(" .")
        if hash_str:
            hash_part = f"_{hash_str}"

    # итоговое имя (ограничиваем общую длину для файловых систем, например 255)
    name = f"{cleaned}{hash_part}"
    if len(name) > 255:
        # обрежем так, чтобы оставить суффикс с хешом нетронутым
        if hash_part:
            max_base = 255 - len(hash_part)
            name = f"{cleaned[:max_base]}{hash_part}"
        else:
            name = name[:255]

    return name


def pack_rdf(loqi: str):
    return [{
        "verb": "hasLoqi",
        "subject": "question",
        "subjectType": "owl:NamedIndividual",
        "object": loqi,
        "objectType": "xsd:string"
    }]


@warnings.deprecated("Use `build_answer_objects_from_cfg` instead for better accuracy")
def build_answer_objects(lines: list[dict[str, list[Any]]], trace_acts: list[TraceAct]):
    ans = []
    for line in lines:
        for button in line.get("buttons", []):
            # Безопасный поиск trace_act с проверкой на None
            trace_act = next(
                filter(
                    lambda ta: ta is not None
                    and ta.cfg_node is not None
                    and ta.cfg_node.metadata is not None
                    and ta.cfg_node.metadata.wrapped_ast is not None
                    and button["node_id"] == ta.cfg_node.metadata.wrapped_ast.ast_node.get("id")
                    and button["type"] == ta.button_type,
                    trace_acts,
                ),
                None  # Возвращаем None, если элемент не найден
            )

            if trace_act is None:
                warnings.warn(
                    f"TraceAct not found for button: node_id={button.get('node_id')}, type={button.get('type')}",
                    stacklevel=2
                )
                continue

            ans.append(
                {
                    "answerId": button["action_id"],
                    "hyperText": button["type"],
                    "domainInfo": f"{trace_act.cfg_node.id}",
                    "concept": "action",
                    "isRightCol": False,
                }
            )
    if len(ans) != len(trace_acts):
        warnings.warn(
            f"len(answer_object) != len(trace_acts): {len(ans)} != {len(trace_acts)}",
                    stacklevel=2
        )
    return ans


def build_answer_objects_from_cfg(
    cfg: CFG,
    lines_data: list[dict[str, list[Any]]],
    include_end_button: bool = False
) -> list[dict[str, Any]]:
    """Строит answerObjects на основе MANDATORY узлов CFG.
    
    Args:
        cfg: Граф потока управления
        lines_data: Данные с кнопками из prepare_interactive_data
        include_end_button: Если False, конечный узел программы исключается (т.е. нельзя будет дать студенту кнопку "Программа завершилась")
    
    Returns:
        Список answerObjects для каждого MANDATORY узла, связанного с кнопкой
    """
    ans = []

    # Собираем все кнопки из lines_data в словарь для быстрого поиска
    # Ключ: (node_id, position), Значение: список button dict
    # position может быть "before" или "after"
    buttons_by_node_and_position: dict[tuple[int | None, str | None], list[dict[str, Any]]] = {}
    buttons_by_node_id: dict[int | None, list[dict[str, Any]]] = {}
    # Множество для отслеживания использованных кнопок (по action_id для уникальности)
    used_button_ids: set[str] = set()
    # Список всех кнопок для проверки неиспользованных
    all_buttons: list[dict[str, Any]] = []
    for line in lines_data:
        for button in line.get("buttons", []):
            all_buttons.append(button)
            node_id = button.get("node_id")
            position = button.get("position")  # "before" или "after"
            if node_id is not None:
                key = (node_id, position)
                if key not in buttons_by_node_and_position:
                    buttons_by_node_and_position[key] = []
                buttons_by_node_and_position[key].append(button)

                # Также сохраняем все кнопки для node_id (для атомарных узлов)
                if node_id not in buttons_by_node_id:
                    buttons_by_node_id[node_id] = []
                buttons_by_node_id[node_id].append(button)

    # Находим все MANDATORY узлы, для которых нужны кнопки в UI
    mandatory_nodes = []
    for node in cfg.nodes.values():
        if not node.is_mandatory():
            continue

        # Исключаем начальный узел программы
        if node == cfg.begin_node:
            continue

        # Опционально исключаем конечный узел программы
        if node == cfg.end_node:
            if not include_end_button:
                continue

        mandatory_nodes.append(node)

    # Связываем узлы с кнопками
    for node in mandatory_nodes:
        # Получаем AST node_id из узла CFG
        if not node.metadata or not node.metadata.wrapped_ast:
            continue

        ast_node_id = node.metadata.wrapped_ast.ast_node.get("id") if node.metadata.wrapped_ast.ast_node else None
        if ast_node_id is None:
            continue

        # Определяем, какие кнопки соответствуют этому узлу
        matched_buttons = []

        if node.kind == NodeKind.BEGIN:
            # Для BEGIN узлов ищем кнопки с position="before"
            matched_buttons = buttons_by_node_and_position.get((ast_node_id, "before"), [])
        elif node.kind == NodeKind.END:
            # Для END узлов ищем кнопки с position="after"
            matched_buttons = buttons_by_node_and_position.get((ast_node_id, "after"), [])
        else:
            # Для атомарных узлов (ATOM) ищем все кнопки для этого node_id
            # Для атомарных действий обычно создается одна кнопка (с position="before"),
            # но мы берем все кнопки для данного node_id на случай, если их несколько
            matched_buttons = buttons_by_node_id.get(ast_node_id, [])

        if not matched_buttons:
            # Если кнопка не найдена, пропускаем узел
            warnings.warn(
                f"No button found for mandatory node {node.id} (kind={node.kind.value}, ast_node_id={ast_node_id})",
                stacklevel=2
            )
            continue

        # Для каждой найденной кнопки создаем answerObject
        for button in matched_buttons:
            button_id = button.get("action_id")
            if button_id:
                used_button_ids.add(button_id)
            ans.append(
                {
                    "answerId": button["action_id"],
                    "hyperText": button["type"],
                    "domainInfo": f"{node.id}",
                    "concept": "action",
                    "isRightCol": False,
                }
            )

    # Проверяем неиспользованные кнопки
    for button in all_buttons:
        button_id = button.get("action_id")
        if button_id and button_id not in used_button_ids:
            node_id = button.get("node_id")
            position = button.get("position")
            button_type = button.get("type")
            warnings.warn(
                f"Button not used: action_id={button_id}, node_id={node_id}, position={position}, type={button_type} "
                f"(no corresponding mandatory CFG node found)",
                stacklevel=2
            )

    return ans


def build_question(language: str,
                   code_snippet: str,
                   debug_question_name: str | None = None
) -> dict[str, Any] | None:
    mt = to_dict(language, code_snippet)
    source_map: dict[str, Any] | None = convert(code_snippet,
                                                language, language,
                                                source_map=True)  # type: ignore
    if mt is None or source_map is None:
        print("No valid meaning tree output", file=sys.stderr)
        return
    tokens = to_tokens(language, source_map["source_code"])
    if tokens is None:
        print("No valid token output", file=sys.stderr)
        return
    htmlgen = CodeHighlightGenerator()
    lines_data = htmlgen.prepare_interactive_data(
        source_map,
        tokens,
    )
    html = htmlgen.generate_html(
        lines_data,
        source_map,
        snippet=True
    )

    loqi, cfg, trace_acts = build_loqi(mt, lines_data)
    if not loqi or not cfg:
        print("No valid loqi output", file=sys.stderr)
        return

    tags = 0
    match language:
        case "python":
            tags |= 8
        case "java":
            tags |= 4
        case "c++":
            tags |= 2

    qname = debug_question_name or create_question_name(mt, code_snippet)
    answ = build_answer_objects_from_cfg(cfg, lines_data, include_end_button=False)
    return {
        "commonQuestion": {
            "questionData": {
                "questionType": "ORDER",
                "questionText": html,
                "questionName": qname,
                "questionDomainType": "OrderActs",
                "options": {
                    "showTrace": True,
                    "requireContext": True,
                    "requireAllAnswers": True,
                    "orderNumberOptions": {"position": "SUFFIX", "delimiter": "/"},
                    "multipleSelectionEnabled": True,
                    "showSupplementaryQuestions": False,
                },
                "answerObjects": answ,
                "statementFacts": pack_rdf(loqi),
            },
            "concepts": find_concepts(mt),
            "tags": find_tags(mt, language),
            "negativeLaws": [],
        },
        "metadataList": [{  # TODO
            "name": qname,
            "domainShortname": "ctrl_flow_dt25",
            "templateId": mt.get("unique_hash", 0),
            "tagBits": tags,
            "conceptBits": 0,
            "lawBits": 0,
            "violationBits": 0,
            "traceConceptBits": 0,
            "solutionStructuralComplexity": 0.5,
            "integralComplexity": 0.5,
            "solutionSteps": len(trace_acts) - 1,  # !!
            "distinctErrorCount": 3,  # !! TODO
            "version": 2,
            "structureHash": mt.get("unique_hash", 0),
            "origin": "debug",
            "originLicense": "Public Domain",
            "treeHashCode": mt.get("unique_hash", 0),
            "skillBits": 0
        }],
    }
