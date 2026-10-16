"""Статический HTML кода задачи и кнопки, из которых строятся ответы."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString

from src.ast_managers import CodeManager
from src.coderenderer.html import (
    extract_buttons_from_context,
    prepare_html_context,
    render_static_html,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


@dataclass(frozen=True, slots=True)
class QuestionHtml:
    # Фрагмент кода с кнопками, без стилей: CSS подключает CompPrehension.
    text: str
    # Кнопки фрагмента в формате extract_buttons_from_context.
    buttons: list[dict[str, Any]]


def render_question_html(code: CodeManager) -> QuestionHtml:
    """HTML кода задачи; у всех задач фрагмента он одинаковый."""
    context = prepare_html_context(code)
    return QuestionHtml(
        text=_minify_question_html(
            render_static_html(context, templates_dir=str(TEMPLATES_DIR), snippet_only=True)
        ),
        buttons=extract_buttons_from_context(context),
    )


def _minify_question_html(html: str) -> str:
    """Remove template comments and formatting, preserving the code tokens verbatim."""
    # BeautifulSoup otherwise collapses whitespace-only spans, including code indentation.
    soup = BeautifulSoup(html, "html.parser", preserve_whitespace_tags={"span"})
    for node in list(soup.descendants):
        if isinstance(node, Comment) or (
            isinstance(node, NavigableString)
            and not node.strip()
            and node.find_parent(class_="token") is None
        ):
            node.extract()
    return str(soup)
