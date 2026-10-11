"""Статический HTML кода задачи и кнопки, из которых строятся ответы."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        text=render_static_html(context, templates_dir=str(TEMPLATES_DIR), snippet_only=True),
        buttons=extract_buttons_from_context(context),
    )
