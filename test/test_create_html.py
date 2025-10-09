from pathlib import Path

from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_tokens

language, ext = "java", "java"

with Path(f"code_example.{ext}").open(encoding="utf-8") as f:
    code = f.read()
source_map = convert(code, language, language, source_map=True)
if source_map is None or not isinstance(source_map, dict):
    raise ValueError("Не удалось получить source_map")
tokens = to_tokens(language, source_map["source_code"])
if not tokens:
    raise ValueError("Не удалось получить токены")
CodeHighlightGenerator().generate_html(
    source_map,
    tokens,
    output_file="output.html",
)
