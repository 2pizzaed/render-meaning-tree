"""Статический HTML кода задачи и кнопки, из которых строятся ответы."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString

from src.coderenderer.html import (
    extract_buttons_from_context,
    prepare_html_context,
    render_static_html,
)
from src.generator.helpers.call_values import CallValueOption, call_value_menus
from src.generator.problems import GenerationOptions
from src.generator.registry import SituationRegistry
from src.generator.serialization import registry_to_loqi

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


@dataclass(frozen=True, slots=True)
class QuestionHtml:
    # Фрагмент кода с кнопками, без стилей: CSS подключает CompPrehension.
    text: str
    # Кнопки фрагмента в формате extract_buttons_from_context.
    buttons: list[dict[str, Any]]
    # Пункты dropdown значений вызова по номеру ответа кнопки step-out.
    call_value_menus: dict[int, tuple[CallValueOption, ...]]


def render_question_html(statement: SituationRegistry) -> QuestionHtml:
    """HTML кода задачи по ситуации условия: пункты dropdown зависят от её значений.

    Флаги - ``GenerationOptions`` конфига ситуации: dropdown вызова и кнопки скобок блоков.
    """
    options = statement.config.options if statement.config else GenerationOptions()
    context = prepare_html_context(
        statement.code, explicit_compound_boundaries=options.explicit_compound_boundaries
    )
    buttons = extract_buttons_from_context(context)
    menus: dict[int, tuple[CallValueOption, ...]] = {}
    if not options.disable_call_dropdown:
        serializer, _ = registry_to_loqi(statement)
        menus = call_value_menus(statement, buttons, serializer)
    context["call_value_menus"] = menus
    return QuestionHtml(
        text=_minify_question_html(
            render_static_html(context, templates_dir=str(TEMPLATES_DIR), snippet_only=True)
        ),
        buttons=buttons,
        call_value_menus=menus,
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
