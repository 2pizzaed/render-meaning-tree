import argparse
import traceback
from pathlib import Path
from typing import Literal

from flask import Flask, render_template, request

from src.ast_managers import CodeManager, prepare_code
from src.coderenderer.html import prepare_html_context
from src.types import SupportedProgrammingLanguage

template_dir = (Path(__file__).parent / "../../templates").absolute()
app = Flask(__name__, template_folder=template_dir)

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
                answer_objects = build_answer_objects(manager, enable_trace=enable_trace)
                context = prepare_html_context(manager, answer_objects=answer_objects)
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def build_answer_objects(manager: CodeManager, *, enable_trace: bool) -> dict[str, str] | None:
    """Temporary hook for answer-trace payload generation."""
    if not enable_trace:
        return None
    return None


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


if __name__ == "__main__":
    raise SystemExit(main())
