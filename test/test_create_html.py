from pathlib import Path

from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_tokens

if __name__ == "__main__":
    language, ext = "python", "py"
    example_path = Path(__file__).parent / "data" / "examples" / f"code_example.{ext}"
    template_path = Path(__file__).parent.parent / "templates" / "base_new.html"

    with example_path.open(encoding="utf-8") as f:
        code = f.read()
    source_map = convert(code, language, language, source_map=True)
    if source_map is None or not isinstance(source_map, dict):
        raise ValueError("Source map generation failure")
    tokens = to_tokens(language, source_map["source_code"])
    if not tokens:
        raise ValueError("Token obtaining failure")
    gen = CodeHighlightGenerator(template_path)
    gen.debug = True
    lines_data = gen.prepare_interactive_data(source_map, tokens)
    gen.generate_html(
        lines_data,
        source_map,
        output_file="test/output/output.html",
    )
