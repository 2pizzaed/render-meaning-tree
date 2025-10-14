from pathlib import Path

from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_tokens

language, ext = "python", "py"
example_path = Path(__file__).parent / "examples" / f"code_example.{ext}"
template_path = Path(__file__).parent.parent / "templates" / "base_new.html"

with example_path.open(encoding="utf-8") as f:
    code = f.read()
source_map = convert(code, language, language, source_map=True)
if source_map is None or not isinstance(source_map, dict):
    raise ValueError("Source map generation failure")
tokens = to_tokens(language, source_map["source_code"])
if not tokens:
    raise ValueError("Token obtaining failure")
CodeHighlightGenerator(template_path).generate_html(
    source_map,
    tokens,
    output_file="output.html",
)
