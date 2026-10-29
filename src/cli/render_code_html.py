"""Статический HTML-сниппет кода (шаблон ``code_component.html``) для файла или stdin."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import get_args

from src.ast_managers import prepare_code
from src.coderenderer.html import prepare_html_context, render_static_html
from src.helpers.files import resolve_project_root
from src.types import SNIPPET_LANGUAGES_BY_SUFFIX, SupportedProgrammingLanguage

# Иконки кнопок - классы Remix Icon (ri-*); версия та же, что в playground.html.
REMIX_ICON_LINK = (
    '<link href="https://cdn.jsdelivr.net/npm/remixicon@4.9.0/fonts/remixicon.css" rel="stylesheet">\n'
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.stdin == (args.code_file is not None):
        parser.error("pass either a code file or --stdin")

    language: SupportedProgrammingLanguage | None = args.lang
    if args.stdin:
        if language is None:
            parser.error("--stdin requires --lang")
        # Код и HTML - в UTF-8, как и файлы, а не в кодировке консоли Windows.
        code = sys.stdin.buffer.read().decode("utf-8")
    else:
        language = language or SNIPPET_LANGUAGES_BY_SUFFIX.get(args.code_file.suffix.lower())
        if language is None:
            parser.error(f"cannot detect language of {args.code_file}, pass --lang")
        code = args.code_file.read_text(encoding="utf-8")

    html = render_code_html(code, language, buttons=not args.no_buttons, style=not args.no_style)
    # Без кнопок иконки не нужны.
    if not (args.no_buttons or args.no_icon_styles):
        html = REMIX_ICON_LINK + html
    if args.output is None:
        sys.stdout.buffer.write(html.encode("utf-8"))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
    return 0


def render_code_html(
    code: str,
    language: SupportedProgrammingLanguage,
    *,
    buttons: bool = True,
    style: bool = True,
) -> str:
    context = prepare_html_context(prepare_code(code, language), buttons=buttons)
    return render_static_html(
        context,
        templates_dir=str(resolve_project_root() / "templates"),
        snippet_only=True,
        remove_snippet_styles=not style,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a code snippet to static HTML (code_component.html template)."
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        type=Path,
        help="Code file; the language is detected by its extension unless --lang is given.",
    )
    parser.add_argument("--stdin", action="store_true", help="Read code from stdin (requires --lang).")
    parser.add_argument(
        "--lang",
        choices=get_args(SupportedProgrammingLanguage.__value__),
        help="Programming language of the code.",
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Write HTML to this file instead of stdout."
    )
    parser.add_argument(
        "--no-buttons", action="store_true", help="Do not insert action buttons into the code."
    )
    parser.add_argument("--no-style", action="store_true", help="Omit the <style> block.")
    parser.add_argument(
        "--no-icon-styles",
        action="store_true",
        help="Do not add the Remix Icon stylesheet link from CDN (button icons).",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
