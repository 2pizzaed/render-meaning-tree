from pathlib import Path

from src.ast_managers import prepare_code
from src.coderenderer.html import prepare_html_context, render_static_html

if __name__ == "__main__":
    language, ext = "python", "py"
    example_path = Path(__file__).parent / "data" / "examples" / f"code_example.{ext}"

    with example_path.open(encoding="utf-8") as f:
        code = f.read()

    manager = prepare_code(code, language)
    context = prepare_html_context(manager)
    render_static_html(
        context,
        output_path="test/output/output.html", snippet_only=True
    )
