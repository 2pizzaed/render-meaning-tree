import re
import sys
from typing import Any
import warnings

from src.cfg.abstractions import InterruptionType, SituationState, load_constructs
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg_builder import CFGBuilder
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.reachability import determine_all_paths_between_opaque_nodes
from src.cfg.trace_builder import all_interactions, build_trace_act
from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_dict, to_tokens


def find_concepts(mt: dict[str, Any]) -> list[str]:
    return []


def find_skills(mt: dict[str, Any]) -> list[str]:
    return []


def find_tags(mt: dict[str, Any]) -> list[str]:
    return []


def build_loqi(ast_json: dict[str, Any], lines: list[dict[str, list[Any]]]) -> str | None:
    constructs = load_constructs("constructs.yml")
    program_root = ASTNodeWrapper(ast_node=ast_json)
    b = CFGBuilder(constructs)
    # Генерируем CFG
    cfg = b.make_cfg_for_ast(program_root)

    if cfg is None:
        return

    # Оптимизируем CFG
    cfg.optimize()

    # Экспортируем в LOQI
    exporter = LoqiExporter()

    exporter.add_object(
        situation := SituationState(
            interruption_state=InterruptionType.NONE,
        )
    )
    exporter.set_var("STATE", situation)

    trace_acts = [
        build_trace_act(cfg, interaction) for interaction in all_interactions(lines)
    ]
    for trace_act in trace_acts:
        exporter.add_object(trace_act)

    # Добавляем пути между узлами
    paths = determine_all_paths_between_opaque_nodes(cfg)
    if paths:
        exporter.add_paths(paths)

    return exporter.export_cfg(cfg, None)


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
    return {
        "verb": "hasLoqi",
        "subject": "question",
        "subjectType": "owl:NamedIndividual",
        "object": loqi,
        "objectType": "xsd:string"
    }


def build_answer_objects(lines: list[dict[str, list[Any]]]):
    ans = []
    for line in lines:
        for button in line.get("buttons", []):
            ans.append({
                "answerId": button["action_id"],
                "hyperText": button["type"],
                "domainInfo": f"ast_{button["node_id"]};{button["type"]}",
                "concept": "action",
                "isRightCol": False
            })
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

    loqi = build_loqi(mt, lines_data)
    if not loqi:
        print("No valid loqi output", file=sys.stderr)
        return

    qname = debug_question_name or create_question_name(mt, code_snippet)
    answ = build_answer_objects(lines_data)
    return {
        "commonQuestion": {
            "questionData": {
                "questionType": "ORDER",
                "questionText": html,
                "questionName": qname,
                "questionDomainType": "OrderActs",
                "questionOptions": {
                    "showTrace": True,
                    "requireContext": False,
                    "requireAllAnswers": True,
                    "orderNumberOptions": {"position": "SUFFIX", "delimiter": "/"},
                    "multipleSelectionEnabled": True,
                    "showSupplementaryQuestions": False,
                },
                "answerObjects": answ,
                "statementFacts": pack_rdf(loqi),
            },
            "concepts": find_concepts(mt),
            "tags": find_tags(mt),
            "negativeLaws": [],
        },
        "metadataList": {  # TODO
            "name": qname,
            "domainShortname": "ctrlFlowDT",
            "templateId": mt.get("unique_hash", 0),
            "tagBits": 0,
            "conceptBits": 0,
            "lawBits": 0,
            "violationBits": 0,
            "traceConceptBits": 0,
            "solutionStructuralComplexity": 0.5,
            "integralComplexity": 0.5,
            "solutionSteps": len(answ),
            "distinctErrorCount": len(answ),
            "version": 2,
            "structureHash": mt.get("unique_hash", 0),
            "origin": "debug",
            "originLicense": "Public Domain",
            "treeHashCode": mt.get("unique_hash", 0),
            "skillBits": 0
        },
    }
