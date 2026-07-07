import argparse
import tempfile
import traceback
from io import BytesIO
from pathlib import Path
from typing import Literal

from flask import Flask, jsonify, render_template, request, send_file

from src.ast_managers import prepare_code
from src.coderenderer.html import extract_buttons_from_context, prepare_html_context
from src.dot import render_dot_png
from src.generator.helpers.ui_trace import (
    apply_trace_action_names,
    resolve_button_action_name,
)
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import registry_to_loqi
from src.helpers.tpg.reasoning import solve_pipeline_reasoning
from src.tpg_domain import ReasoningResult, TreeNode
from src.types import SupportedProgrammingLanguage
from test.helpers.dot import trace_acts_to_dot
from test.scripts.find_correct_trace_actions import build_correct_trace_pipeline

template_dir = (Path(__file__).parent / "../../templates").absolute()
app = Flask(__name__, template_folder=template_dir)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYGROUND_REASON_MODEL_DIR = PROJECT_ROOT / "domain"
PLAYGROUND_REASON_TREE: str | None = None
PLAYGROUND_REASON_TIME_LIMIT_SECONDS = 30

LANGUAGE_OPTIONS: tuple[tuple[SupportedProgrammingLanguage, str], ...] = (
    ("java", "Java"),
    ("python", "Python"),
    ("c++", "C++"),
)

def read_language(value: str | None, default: SupportedProgrammingLanguage) -> SupportedProgrammingLanguage:
    if value == "java" or value == "python" or value == "c++":
        return value
    return default


def read_target_language(value: str | None) -> SupportedProgrammingLanguage | Literal[""]:
    if not value or (value != "java" and value != "python" and value != "c++"):
        return ""
    return value


@app.route("/", methods=["GET", "POST"])
def index():
    code = ""
    language: SupportedProgrammingLanguage = "java"
    target_language: SupportedProgrammingLanguage | Literal[""] = ""
    enable_trace = True
    context = {
        "lines": [],
        "nodes_json": "{}",
        "enable_trace": enable_trace,
        "answer_objects": None,
        "answer_objects_json": "",
    }
    error = None

    if request.method == "POST":
        code = request.form.get("code", "")
        language = read_language(request.form.get("language"), "java")
        target_language = read_target_language(request.form.get("target_language"))

        if not language:
            error = "No language specified"
        else:
            try:
                manager = prepare_code(code, language, target_language=target_language or None)
                context = prepare_html_context(manager, answer_objects={})
                answer_objects = build_answer_objects(
                    manager,
                    context,
                    enable_trace=enable_trace,
                )
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
    context["language_options"] = LANGUAGE_OPTIONS

    return render_template(
        "playground.html",
        error=error,
        **context,  # Распаковываем словарь контекста в аргументы шаблона
    )


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

    try:
        manager = prepare_code(
            code,
            language,
            target_language=target_language or None,
        )
        pipeline = DomainDataGeneratorPipeline(manager, fork_enabled=False)
        pipeline.process()
        apply_trace_action_names(pipeline, selected_trace)
        reasoning_tmp = _playground_temp_dir("playground-reason-")
        reasoning = solve_pipeline_reasoning(
            reasoning_tmp,
            pipeline,
            model_dir=PLAYGROUND_REASON_MODEL_DIR,
            filename="playground-trace.loqi",
            tree=PLAYGROUND_REASON_TREE,
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=PLAYGROUND_REASON_TIME_LIMIT_SECONDS,
            restore_exported_trace=False,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e!s}"}), 500

    return jsonify(
        {
            "ok": True,
            "trace": selected_trace,
            "reasoning": serialize_reasoning_result(reasoning.result),
        }
    )


@app.post("/trace-png")
def trace_png():
    code = request.form.get("code", "")
    language = read_language(request.form.get("language"), "java")

    try:
        pipeline = build_correct_trace_pipeline(
            code,
            language=language,
            time_limit_seconds=PLAYGROUND_REASON_TIME_LIMIT_SECONDS,
        )
        dot_text = trace_acts_to_dot(
            pipeline.registry.trace_acts,
            name="playground_correct_trace",
        )
        png_tmp = _playground_temp_dir("playground-trace-png-")
        png_path = render_dot_png(dot_text, png_tmp / "correct-trace.png")
        png_bytes = png_path.read_bytes()
    except Exception as e:
        traceback.print_exc()
        return f"{type(e).__name__}: {e!s}", 500, {"Content-Type": "text/plain; charset=utf-8"}

    return send_file(
        BytesIO(png_bytes),
        mimetype="image/png",
        download_name="correct-trace.png",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def build_answer_objects(
    manager,
    context: dict[str, object],
    *,
    enable_trace: bool,
) -> dict[str, object] | None:
    """Temporary hook for answer-trace payload generation."""
    if not enable_trace:
        return None
    pipeline = DomainDataGeneratorPipeline(manager, fork_enabled=False)
    pipeline.process()
    serializer, _ = registry_to_loqi(pipeline.registry)
    return {
        str(button["action_id"]): resolve_button_action_name(
            pipeline,
            button,
            serializer=serializer,
        )
        for button in extract_buttons_from_context(context)
        if button.get("action_id") is not None
    }


def serialize_reasoning_result(result: ReasoningResult) -> dict[str, object]:
    final_node = result.final_node
    exception_names = [
        exception.exception_name
        for exception in result.exceptions
        if exception.exception_name
    ]
    final_exception_name = _first_metadata_value(final_node, "exceptionName")
    if final_exception_name:
        exception_names.append(final_exception_name)

    has_exception = _has_metadata(final_node, "exception") or bool(result.exceptions)
    status = "correct" if result.result is True else "error" if result.result is False else "unknown"

    return {
        "result": result.result,
        "status": status,
        "hasException": has_exception,
        "exceptionNames": exception_names,
        "explanations": _metadata_values(final_node, "explanation"),
        "skills": _metadata_values(final_node, "skill"),
        "variables": result.variables,
    }


def _metadata_values(node: TreeNode | None, name: str) -> list[str]:
    if node is None:
        return []
    grouped: dict[str | None, list[str]] = {}
    for entry in node.metadata:
        if entry.name == name and entry.value is not None:
            grouped.setdefault(entry.loc_code, []).append(str(entry.value))
    return grouped.get("EN") or grouped.get("en") or grouped.get(None) or [
        value for values in grouped.values() for value in values
    ]


def _first_metadata_value(node: TreeNode | None, name: str) -> str | None:
    values = _metadata_values(node, name)
    return values[0] if values else None


def _has_metadata(node: TreeNode | None, name: str) -> bool:
    return bool(_metadata_values(node, name))


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
    return parser.parse_args(argv)


def _playground_temp_root() -> Path:
    tmp_root = PROJECT_ROOT / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root


def _playground_temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix, dir=_playground_temp_root()))


if __name__ == "__main__":
    raise SystemExit(main())
