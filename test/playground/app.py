import argparse
import traceback
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cache, lru_cache
from io import BytesIO
from pathlib import Path
from typing import Literal

from flask import Flask, jsonify, render_template, request, send_file

from src.ast_managers import prepare_code
from src.cli.find_correct_trace_actions import solve_correct_trace
from src.coderenderer.html import extract_buttons_from_context, prepare_html_context
from src.dot import render_dot_svg
from src.generator.compprehension_serializer import (
    QuestionTemplateError,
    problem_to_question_template,
)
from src.generator.helpers.actions import resolve_trace_steps
from src.generator.helpers.call_values import (
    call_value_domain_info,
    call_value_menus,
    is_annotated_call_end,
)
from src.generator.helpers.ui_trace import resolve_button_action_name
from src.generator.pipeline import LearningProblemGeneratorPipeline
from src.generator.problems import LearningProblem
from src.generator.question_html import render_question_html
from src.generator.registry import SituationRegistry
from src.generator.serialization import registry_to_loqi
from src.generator.utilities import code_manager_to_registry, problem_statement_registry
from src.helpers.files import make_project_temp_dir
from src.helpers.tpg import (
    NextCorrectActionOutput,
    PipelineReasoningOutput,
    TraceStep,
    check_graph_stepwise_reasoning,
    find_graph_next_correct_action,
    restore_trace_from_loqi,
)
from src.helpers.tpg.explanations import (
    DEFAULT_MORE_LABEL,
    ExplanationType,
    collect_explanations_from_trace,
    collect_unique_skills,
    explanation_view,
    flatten_explanation_texts,
)
from src.helpers.tpg.loqi_values import LoqiPropertyResolver
from src.model.situation import Action
from src.serialization.loqi import LoqiRenderIndex, LoqiSerializer
from src.tpg_domain import ReasoningResult, TreeNode
from src.types import SupportedProgrammingLanguage
from test.helpers.dot import trace_acts_to_dot

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYGROUND_REASON_MODEL_DIR = PROJECT_ROOT / "domain"
PLAYGROUND_REASON_TREE: str | None = None
PLAYGROUND_REASON_TIME_LIMIT_SECONDS = 30
PLAYGROUND_SNIPPETS_DIR = PROJECT_ROOT / "test" / "data"
# Ситуаций (код, языки, seed) в памяти: генерация задачи по seed занимает до минут.
PLAYGROUND_SITUATION_CACHE_SIZE = 16
# Принятых префиксов трассы в памяти; одна запись - экспортированный LOQI ситуации, ~70 КБ.
PLAYGROUND_PREFIX_CACHE_SIZE = 256
# Расширение файла примера → исходный язык playground.
SNIPPET_LANGUAGES_BY_SUFFIX: dict[str, SupportedProgrammingLanguage] = {
    ".java": "java",
    ".py": "python",
    ".cpp": "c++",
    ".cc": "c++",
    ".cxx": "c++",
    ".hpp": "c++",
    ".hh": "c++",
    ".h": "c++",
}

template_dir = (Path(__file__).parent / "../../templates").absolute()
app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=template_dir / "static",
    static_url_path="/static",
)
app.config["SNIPPETS_DIR"] = PLAYGROUND_SNIPPETS_DIR

LANGUAGE_OPTIONS: tuple[tuple[SupportedProgrammingLanguage, str], ...] = (
    ("java", "Java"),
    ("python", "Python"),
    ("c++", "C++"),
)

def read_language(value: str | None, default: SupportedProgrammingLanguage) -> SupportedProgrammingLanguage:
    if value == "java" or value == "python" or value == "c++":
        return value
    return default


def format_error(error: BaseException) -> str:
    # format_exception_only включает __notes__ (итерация решателя, путь к LOQI) и
    # многострочную диагностику ReasoningCallError (причина, переменные, выражение).
    return "".join(traceback.format_exception_only(error)).rstrip()


def read_target_language(value: str | None) -> SupportedProgrammingLanguage | Literal[""]:
    if not value or (value != "java" and value != "python" and value != "c++"):
        return ""
    return value


def read_seed(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text else None


@dataclass(frozen=True, slots=True)
class PlaygroundSituation:
    # Не изменяется: рассуждатель достраивает трассу, поэтому запросы берут registry.clone().
    registry: SituationRegistry
    # Вариант значений и исходный LOQI задачи генератора; None у ситуации по умолчанию.
    problem: str | None = None
    problem_loqi: str | None = None
    # Для экспорта вопросов: задачи генератора по убыванию Q и исходная ситуация
    # фрагмента (registry генератора после ветвления); пусты у ситуации по умолчанию.
    problems: tuple[LearningProblem, ...] = ()
    base_registry: SituationRegistry | None = None


@lru_cache(maxsize=PLAYGROUND_SITUATION_CACHE_SIZE)
def load_situation(
    code: str,
    language: SupportedProgrammingLanguage,
    target_language: SupportedProgrammingLanguage | Literal[""],
    seed: int | None,
) -> PlaygroundSituation:
    """Ситуация по умолчанию, а при seed — первая по Q задача генератора."""
    manager = prepare_code(code, language, target_language=target_language or None)
    if seed is None:
        return PlaygroundSituation(code_manager_to_registry(manager))

    pipeline = LearningProblemGeneratorPipeline.from_code(manager, seed=seed)
    problems = pipeline.run().results()
    if not problems:
        reason = pipeline.termination_reason or "all value variants were rejected, see the server log"
        raise ValueError(f"No problems generated for seed {seed}: {reason}")
    # results() упорядочены по номеру варианта, сортировка устойчива: из равных по Q
    # первой остаётся задача с меньшим номером варианта.
    problems = sorted(problems, key=lambda problem: -(problem.score or 0.0))
    problem = problems[0]

    # Ситуация условия задачи: корневой акт и значения задачи, трасса строится заново.
    registry = problem_statement_registry(pipeline.registry, problem)
    _, problem_loqi = registry_to_loqi(registry)
    return PlaygroundSituation(
        registry,
        problem=f"{problem.variant}; N={problem.steps}; Q={problem.score or 0.0:.2f}",
        problem_loqi=problem_loqi,
        problems=tuple(problems),
        base_registry=pipeline.registry,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    code = ""
    language: SupportedProgrammingLanguage = "java"
    target_language: SupportedProgrammingLanguage | Literal[""] = ""
    seed_text = ""
    enable_trace = True
    export_situation: dict[str, object] | None = None
    context = {
        "lines": [],
        "nodes_json": "{}",
        "source_map": None,
        "enable_trace": enable_trace,
        "answer_objects": None,
        "answer_objects_json": "",
    }
    error = None

    if request.method == "POST":
        code = request.form.get("code", "")
        language = read_language(request.form.get("language"), "java")
        target_language = read_target_language(request.form.get("target_language"))
        seed_text = request.form.get("seed", "").strip()

        if not language:
            error = "No language specified"
        else:
            try:
                situation = load_situation(code, language, target_language, read_seed(seed_text))
                registry = situation.registry.clone()
                context = prepare_html_context(registry.code, answer_objects={})
                answer_objects = build_answer_objects(
                    registry,
                    context,
                    enable_trace=enable_trace,
                )
                context["problem"] = situation.problem
                context["problem_loqi"] = situation.problem_loqi
                context["answer_objects"] = answer_objects
                context["answer_objects_json"] = (
                    app.json.dumps(answer_objects, ensure_ascii=False, indent=4)
                    if answer_objects
                    else ""
                )
                context["code"] = code
                context["language"] = language
                context["target_language"] = target_language
                context["enable_trace"] = enable_trace
                # Параметры отрисованной ситуации: экспорт не зависит от правок формы после Render.
                export_situation = {
                    "code": code,
                    "language": language,
                    "target_language": target_language,
                    "seed": seed_text,
                    "questionCount": len(situation.problems),
                }

            except Exception as e:
                traceback.print_exc()
                error = f"{type(e).__name__}: {e!s}"
                # Возвращаем базовый контекст, чтобы шаблон не упал
                context["code"] = code
                context["language"] = language
                context["target_language"] = target_language
                context["enable_trace"] = enable_trace

    context.setdefault("code", code)
    context.setdefault("language", language)
    context.setdefault("target_language", target_language)
    context.setdefault("enable_trace", enable_trace)
    context["seed"] = seed_text
    context["export_situation"] = export_situation
    context["language_options"] = LANGUAGE_OPTIONS
    context["snippet"] = request.form.get("snippet", "") if request.method == "POST" else ""
    context["snippet_options"] = list_snippet_files(_snippets_dir())

    return render_template(
        "playground.html",
        error=error,
        **context,  # Распаковываем словарь контекста в аргументы шаблона
    )


@app.get("/snippet")
def snippet():
    relative_path = request.args.get("path", "")
    snippet_file = resolve_snippet_file(_snippets_dir(), relative_path)
    if snippet_file is None:
        return jsonify({"ok": False, "error": f"Snippet not found: {relative_path}"}), 404
    try:
        code = snippet_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return jsonify({"ok": False, "error": format_error(e)}), 500
    return jsonify(
        {
            "ok": True,
            "path": relative_path,
            "code": code,
            "language": SNIPPET_LANGUAGES_BY_SUFFIX[snippet_file.suffix.lower()],
        }
    )


def list_snippet_files(root: Path) -> list[str]:
    """Пути примеров относительно root (через `/`), язык которых определяется по расширению."""
    if not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SNIPPET_LANGUAGES_BY_SUFFIX
    )


def resolve_snippet_file(root: Path, relative_path: str) -> Path | None:
    if not relative_path:
        return None
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    # Не выпускаем запрос за пределы папки примеров (../, абсолютные пути).
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    if candidate.suffix.lower() not in SNIPPET_LANGUAGES_BY_SUFFIX:
        return None
    return candidate


def _snippets_dir() -> Path:
    return Path(app.config["SNIPPETS_DIR"])


@app.post("/reason-trace")
def reason_trace():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "")
    language = read_language(payload.get("language"), "java")
    target_language = read_target_language(payload.get("target_language"))
    selected_trace = payload.get("trace")
    if not isinstance(selected_trace, list) or not all(
        isinstance(step, str) for step in selected_trace
    ):
        return jsonify({"ok": False, "error": "Trace payload must be a list of strings."}), 400

    reasoning_tmp: Path | None = None
    try:
        situation_key = (code, language, target_language, read_seed(payload.get("seed")))
        registry = load_situation(*situation_key).registry.clone()
        serializer, _ = registry_to_loqi(registry)
        selected_steps = resolve_trace_steps(serializer, selected_trace)
        selected_actions = [step.action for step in selected_steps]
        trace_start = len(registry.trace_acts)
        reasoning_tmp = _playground_temp_dir("playground-reason-")
        reasoning = check_trace_steps(
            reasoning_tmp,
            registry,
            selected_trace,
            selected_steps,
            situation_key=situation_key,
            use_cache=payload.get("no_cache") is not True,
            filename="playground-trace.loqi",
            json_trace=True,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify(
            {"ok": False, "error": format_error(e), "loqi": _latest_loqi_text(reasoning_tmp)}
        ), 500

    serialized = serialize_reasoning_result(reasoning.result)
    confirmed_count = (
        len(selected_actions) if serialized["status"] == "correct" and not serialized["hasException"]
        else reasoning.step_index or 0
    )
    return jsonify(
        {
            "ok": True,
            "trace": selected_trace,
            # Шаг, который клиент заменит следующим выбранным действием.
            "failedStepIndex": (
                reasoning.step_index if serialized["status"] != "correct" else None
            ),
            "reasoning": serialized,
            "traceHints": build_trace_hints(registry, selected_actions[:confirmed_count], trace_start),
            "loqi": reasoning.loqi_text,
        }
    )


@app.post("/hint-trace")
def hint_trace():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "")
    language = read_language(payload.get("language"), "java")
    target_language = read_target_language(payload.get("target_language"))
    selected_trace = payload.get("trace")
    if not isinstance(selected_trace, list) or not all(
        isinstance(step, str) for step in selected_trace
    ):
        return jsonify({"ok": False, "error": "Trace payload must be a list of strings."}), 400

    hint_tmp: Path | None = None
    try:
        situation_key = (code, language, target_language, read_seed(payload.get("seed")))
        registry = load_situation(*situation_key).registry.clone()
        serializer, _ = registry_to_loqi(registry)
        selected_steps = resolve_trace_steps(serializer, selected_trace)
        selected_actions = [step.action for step in selected_steps]
        trace_start = len(registry.trace_acts)
        hint_tmp = _playground_temp_dir("playground-hint-")
        if selected_steps:
            # Восстанавливаем трассу (с прозрачными актами) пошаговой проверкой.
            checked = check_trace_steps(
                hint_tmp,
                registry,
                selected_trace,
                selected_steps,
                situation_key=situation_key,
                use_cache=payload.get("no_cache") is not True,
                filename="playground-hint-check.loqi",
            )
            if checked.result.result is not True or checked.result.exceptions:
                step = (checked.step_index or 0) + 1
                return jsonify(
                    {
                        "ok": False,
                        "error": f"Trace is incorrect at step {step}; fix it before requesting a hint.",
                        "loqi": checked.loqi_text,
                        "traceHints": build_trace_hints(
                            registry, selected_actions[:checked.step_index or 0], trace_start,
                        ),
                    }
                ), 409
        hint = find_graph_next_correct_action(
            hint_tmp,
            registry,
            model_dir=PLAYGROUND_REASON_MODEL_DIR,
            filename="playground-hint.loqi",
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=PLAYGROUND_REASON_TIME_LIMIT_SECONDS,
        )
        action_name = hint_step_name(serializer, hint)
    except Exception as e:
        traceback.print_exc()
        return jsonify(
            {"ok": False, "error": format_error(e), "loqi": _latest_loqi_text(hint_tmp)}
        ), 500

    return jsonify(
        {
            "ok": True,
            "trace": selected_trace,
            "finished": hint.finished,
            "action": action_name,
            "traceHints": build_trace_hints(
                registry,
                [*selected_actions, hint.action] if hint.action is not None else selected_actions,
                trace_start,
            ),
            "loqi": hint.output.loqi_text,
        }
    )


@app.post("/export-question")
def export_question():
    """Вопрос CompPrehension по задаче с номером ``index`` (по убыванию Q) для seed."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "")
    language = read_language(payload.get("language"), "java")
    target_language = read_target_language(payload.get("target_language"))
    index = payload.get("index")
    if not isinstance(index, int) or isinstance(index, bool):
        return jsonify({"ok": False, "error": "Question index must be an integer."}), 400

    try:
        seed = read_seed(payload.get("seed"))
        if seed is None:
            return jsonify({"ok": False, "error": "Questions are exported only for a seed."}), 400
        situation = load_situation(code, language, target_language, seed)
        if situation.base_registry is None or not 0 <= index < len(situation.problems):
            return jsonify({"ok": False, "error": f"No problem #{index} for seed {seed}."}), 400
        problem = situation.problems[index]
        statement = problem_statement_registry(situation.base_registry, problem)
        question = problem_to_question_template(
            problem, statement, render_question_html(statement)
        )
    except QuestionTemplateError as e:
        app.logger.warning("Question #%d for seed %s skipped: %s", index, payload.get("seed"), e)
        return jsonify({"ok": False, "skipped": True, "error": str(e)}), 422
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": format_error(e)}), 500

    return jsonify(
        {
            "ok": True,
            "name": question["commonQuestion"]["questionData"]["questionName"],
            "question": question,
        }
    )


@app.post("/clear-cache")
def clear_cache():
    load_situation.cache_clear()
    _checked_prefixes.clear()
    return jsonify({"ok": True})


# Экспортированный LOQI ситуации после принятого префикса трассы. Ключ - ситуация,
# файлы модели и шаги префикса: правка графа не продолжает проверку со старых состояний.
_checked_prefixes: OrderedDict[tuple[object, ...], str] = OrderedDict()


def check_trace_steps(
    directory: Path,
    registry: SituationRegistry,
    trace: Sequence[str],
    steps: Sequence[TraceStep],
    *,
    situation_key: tuple[object, ...],
    use_cache: bool,
    filename: str,
    json_trace: bool = False,
) -> PipelineReasoningOutput:
    """Пошаговая проверка трассы; с ``use_cache`` - от самого длинного принятого префикса.

    Последний шаг проверяется всегда: его результат нужен ответу. Принятая трасса
    запоминается и без ``use_cache``.
    """
    model_key = (*situation_key, _model_fingerprint())
    start = 0
    if use_cache:
        start = next(
            (size for size in range(len(steps) - 1, 0, -1)
             if (*model_key, *trace[:size]) in _checked_prefixes),
            0,
        )
    if start:
        cached_key = (*model_key, *trace[:start])
        _checked_prefixes.move_to_end(cached_key)
        restore_trace_from_loqi(_checked_prefixes[cached_key], registry)
    output = check_graph_stepwise_reasoning(
        directory,
        registry,
        steps[start:],
        model_dir=PLAYGROUND_REASON_MODEL_DIR,
        filename=filename,
        tree=PLAYGROUND_REASON_TREE,
        export_domain=True,
        debug_enabled=True,
        json_trace=json_trace,
        time_limit_seconds=PLAYGROUND_REASON_TIME_LIMIT_SECONDS,
    )
    if output.result.result is True and not output.result.exceptions and output.exported_loqi:
        _checked_prefixes[(*model_key, *trace)] = output.exported_loqi
        _checked_prefixes.move_to_end((*model_key, *trace))
        while len(_checked_prefixes) > PLAYGROUND_PREFIX_CACHE_SIZE:
            _checked_prefixes.popitem(last=False)
    # Индекс шага - в полной трассе, а не в проверенном остатке.
    return replace(output, step_index=start + (output.step_index or 0)) if start else output


def _model_fingerprint() -> tuple[tuple[str, int], ...]:
    # Модель читается из файлов верхнего уровня каталога, без вложенных папок.
    return tuple(
        (path.name, path.stat().st_mtime_ns)
        for path in sorted(PLAYGROUND_REASON_MODEL_DIR.iterdir())
        if path.is_file()
    )


@app.post("/tracing")
def tracing():
    code = request.form.get("code", "")
    language = read_language(request.form.get("language"), "java")
    target_language = read_target_language(request.form.get("target_language"))

    try:
        solver_stops: set[int] = set()
        registry = load_situation(
            code, language, target_language, read_seed(request.form.get("seed"))
        ).registry.clone()
        solve_correct_trace(
            registry,
            time_limit_seconds=PLAYGROUND_REASON_TIME_LIMIT_SECONDS,
            temp_root=_playground_temp_root(),
            solver_stops=solver_stops,
        )
        dot_text = trace_acts_to_dot(
            registry.trace_acts,
            name="playground_correct_trace",
            solver_stops=solver_stops,
        )
        svg_tmp = _playground_temp_dir("playground-tracing-")
        svg_path = render_dot_svg(dot_text, svg_tmp / "correct-trace.svg")
        svg_bytes = svg_path.read_bytes()
    except Exception as e:
        traceback.print_exc()
        return format_error(e), 500, {"Content-Type": "text/plain; charset=utf-8"}

    return send_file(
        BytesIO(svg_bytes),
        mimetype="image/svg+xml",
        download_name="correct-trace.svg",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    app.config["SNIPPETS_DIR"] = args.snippets_dir
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def build_answer_objects(
    registry: SituationRegistry,
    context: dict[str, object],
    *,
    enable_trace: bool,
) -> dict[str, object] | None:
    """Temporary hook for answer-trace payload generation.

    Также записывает в ``context["call_value_menus"]`` пункты dropdown значений вызова:
    у них свои номера ответов.
    """
    if not enable_trace:
        return None
    serializer, _ = registry_to_loqi(registry)
    buttons = extract_buttons_from_context(context)
    answers: dict[str, object] = {
        str(button["action_id"]): resolve_button_action_name(
            registry,
            button,
            serializer=serializer,
        )
        for button in buttons
        if button.get("action_id") is not None
    }
    # Пункты dropdown значений вызова: шаблон кода выводит их у кнопок step-out.
    menus = call_value_menus(registry, buttons, serializer)
    context["call_value_menus"] = menus
    for options in menus.values():
        answers.update({str(option.answer_id): option.domain_info for option in options})
    return answers


def hint_step_name(serializer: LoqiSerializer, hint: NextCorrectActionOutput) -> str | None:
    """Шаг трассы подсказки: у END размеченного вызова - вместе с правильным значением,
    как у пункта dropdown."""
    if hint.action is None:
        return None
    if hint.value is not None and is_annotated_call_end(hint.action):
        step = call_value_domain_info(serializer, hint.action, hint.value)
        if step is not None:
            return step
    action_name = serializer.object_name(hint.action)
    if action_name is None:
        raise LookupError("findCorrect returned an action without a LOQI name")
    return action_name


def build_trace_hints(
    registry: SituationRegistry, selected_actions: Sequence[Action], trace_start: int,
) -> list[str | None]:
    """Hints of confirmed steps, using each TraceAct's hasValue in the LOQI representation."""
    if not selected_actions:
        return []
    serializer, _ = registry_to_loqi(registry)
    loqi = LoqiRenderIndex(serializer.render_result())
    acts = iter(registry.trace_acts[trace_start:])
    hints: list[str | None] = []
    for action in selected_actions:
        act = next((act for act in acts if act.action is action), None)
        if act is None:
            break
        name = serializer.object_name(act)
        obj = loqi.object(name) if name is not None else None
        value = loqi.target(obj, "hasValue") if obj is not None else None
        hint = loqi.metadata_value(value, "hint") if value is not None else None
        hints.append(hint if isinstance(hint, str) and hint else None)
    return hints


def _explanation_properties(result: ReasoningResult) -> LoqiPropertyResolver | None:
    """``${X.prop}`` в объяснениях: значения свойств — из экспортированной ситуации,
    localizedName значений перечислений — из domain.loqi модели."""
    exported = result.artifacts.get("specificDomain")
    if not isinstance(exported, str):
        return None
    return LoqiPropertyResolver(exported, _model_domain_loqi())


@cache
def _model_domain_loqi() -> str:
    return (PLAYGROUND_REASON_MODEL_DIR / "domain.loqi").read_text(encoding="utf-8")


def serialize_reasoning_result(result: ReasoningResult) -> dict[str, object]:
    final_node = result.final_node
    trace = result.trace if isinstance(result.trace, dict) else None

    exception_names = [
        exception.exception_name
        for exception in result.exceptions
        if exception.exception_name
    ]
    final_exception_name = _first_metadata_value(final_node, "exceptionName")
    if final_exception_name:
        exception_names.append(final_exception_name)

    has_exception = _has_exception_node(final_node) or bool(result.exceptions)
    status = "correct" if result.result is True else "error" if result.result is False else "unknown"

    # Объяснения и навыки берём из агрегации по всей трассе, а не только из finalNode.
    # Требуется структурная (JSON) трасса — иначе откатываемся на метаданные finalNode.
    explanation_type = (
        ExplanationType.HINT if result.result is True else ExplanationType.ERROR
    )
    if trace is not None:
        explanation_tree = collect_explanations_from_trace(explanation_type, trace)
        properties = _explanation_properties(result)
        localized_explanations = {
            loc_code: {
                "explanations": flatten_explanation_texts(
                    explanation_tree,
                    loc_code=loc_code,
                    more_label=more_label,
                    variables=result.variable_objects,
                    properties=properties,
                ),
                "explanationView": explanation_view(
                    explanation_tree,
                    loc_code=loc_code,
                    more_label=more_label,
                    variables=result.variable_objects,
                    properties=properties,
                ),
            }
            for loc_code, more_label in (
                ("RU", "И ещё {count} подобных объяснений..."),
                ("EN", DEFAULT_MORE_LABEL),
            )
        }
        skills = collect_unique_skills(trace)
    else:
        localized_explanations = {
            loc_code: {
                "explanations": _metadata_values(final_node, "explanation", loc_code),
                "explanationView": None,
            }
            for loc_code in ("RU", "EN")
        }
        skills = _metadata_values(final_node, "skill")

    return {
        "result": result.result,
        "status": status,
        "hasException": has_exception,
        "exceptionNames": exception_names,
        "finalNode": _serialize_tree_node(final_node),
        **localized_explanations["EN"],
        "localizedExplanations": localized_explanations,
        "skills": skills,
        "variables": result.variables,
    }


def _serialize_tree_node(node: TreeNode | None) -> dict[str, object] | None:
    if node is None:
        return None
    payload: dict[str, object] = {
        "nodeType": node.node_type,
        "metadata": [
            _serialize_tree_node_metadata_entry(entry)
            for entry in node.metadata
        ],
    }
    if node.children is not None:
        payload["children"] = {
            "total": node.children.total,
            "descriptors": [
                {
                    "id": descriptor.id,
                    "line": descriptor.line,
                    "skill": descriptor.skill,
                }
                for descriptor in node.children.descriptors
            ],
        }
    return payload


def _serialize_tree_node_metadata_entry(entry) -> dict[str, object]:
    return {
        "name": entry.name,
        "locCode": entry.loc_code,
        "value": entry.value,
    }


def _metadata_values(node: TreeNode | None, name: str, loc_code: str = "EN") -> list[str]:
    if node is None:
        return []
    grouped: dict[str | None, list[str]] = {}
    for entry in node.metadata:
        if entry.name == name and entry.value is not None:
            grouped.setdefault(entry.loc_code, []).append(str(entry.value))
    return (
        grouped.get(loc_code)
        or grouped.get(loc_code.lower())
        or grouped.get(None)
        or grouped.get("EN")
        or grouped.get("en")
        or [value for values in grouped.values() for value in values]
    )


def _first_metadata_value(node: TreeNode | None, name: str) -> str | None:
    values = _metadata_values(node, name)
    return values[0] if values else None


def _has_metadata(node: TreeNode | None, name: str) -> bool:
    return bool(_metadata_values(node, name))


def _has_exception_node(node: TreeNode | None) -> bool:
    if node is None:
        return False
    node_type = node.node_type.lower()
    if "exception" in node_type or "error" in node_type:
        return True
    return _has_metadata(node, "exception") or _has_metadata(node, "exceptionName")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the playground Flask app.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on.",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable Flask debug mode.",
    )
    parser.add_argument(
        "--snippets-dir",
        type=Path,
        default=PLAYGROUND_SNIPPETS_DIR,
        help="Directory with code examples (searched recursively; language is taken from the file extension).",
    )
    return parser.parse_args(argv)


def _playground_temp_root() -> Path:
    tmp_root = PROJECT_ROOT / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root


def _playground_temp_dir(prefix: str) -> Path:
    return make_project_temp_dir(prefix, _playground_temp_root())


def _latest_loqi_text(directory: Path | None) -> str | None:
    """LOQI, поданный в reasoner последним: нужен для диагностики упавшего запуска."""
    if directory is None:
        return None
    loqi_files = sorted(directory.glob("*.loqi"), key=lambda path: path.stat().st_mtime)
    return loqi_files[-1].read_text(encoding="utf-8") if loqi_files else None


if __name__ == "__main__":
    raise SystemExit(main())
