import traceback
from pathlib import Path

from flask import Flask, render_template, request

from src.ast_managers import prepare_code
from src.coderenderer.html import prepare_html_context

template_dir = (Path(__file__).parent / "../../templates").absolute()
app = Flask(__name__, template_folder=template_dir)


@app.route("/", methods=["GET", "POST"])
def index():
    code = ""
    language = "java"
    context = {"lines": [], "nodes_json": "{}", "enable_trace": False}
    error = None

    if request.method == "POST":
        code = request.form.get("code", "")
        language = request.form.get("language")

        if not language:
            error = "No language specified"
        else:
            try:
                manager = prepare_code(code, language)
                context = prepare_html_context(manager)

            except Exception as e:
                traceback.print_exc()
                error = f"{type(e).__name__}: {e!s}"
                # Возвращаем базовый контекст, чтобы шаблон не упал
                context["code"] = code
                context["language"] = language

    return render_template(
        "playground.html",
        error=error,
        **context,  # Распаковываем словарь контекста в аргументы шаблона
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
