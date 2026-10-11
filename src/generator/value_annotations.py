"""Ручная разметка значений условий комментарием ``<! … >``.

Комментарий-маркер стоит в заголовке цикла или ветви и задаёт цепочку значений
условия целиком (см. ``docs/ideas/value_annotations_idea.md``). Привязка идёт по
дереву: от узла, к которому MT прикрепил комментарий, вверх до ближайшей конструкции
с условием, не заходя в её тело.
"""

from __future__ import annotations

import re

from src.ast_managers import CodeManager, NodePathElement
from src.coderenderer.entities import RendererEntity, Token
from src.generator.registry import SituationRegistry
from src.generator.value_marker import (
    ValueMarkerSyntaxError,
    format_value_marker,
    is_value_marker,
    parse_value_marker,
)
from src.model.situation import Action, ValueAnnotation

# Префикс однострочного комментария в тексте токена.
_COMMENT_PREFIX_RE = re.compile(r"^\s*(?:#|//)")
# Поля, через которые владелец комментария попадает в тело конструкции.
_BODY_FIELDS = frozenset({"body", "elseBranch", "statements"})
# Конструкции, у которых условие стоит после тела. Комментарий в конце их последней
# строки MT отдаёт самому узлу конструкции; у остальных такая строка - строка тела
# (например, ``if (a) x = 1; // …``).
_TRAILING_CONDITION_TYPES = frozenset({"do_while_loop"})


class ValueAnnotationError(ValueError):
    """Ошибка разметки; сообщение готово для лога."""


def is_value_marker_token(entity: RendererEntity) -> bool:
    """Токен комментария-маркера: в коде задачи его не показывают."""
    return (
        isinstance(entity, Token)
        and entity.type == "comment"
        and is_value_marker(_COMMENT_PREFIX_RE.sub("", entity.value, count=1))
    )


def strip_value_markers(code: CodeManager) -> str:
    """Код без комментариев-маркеров в конце строк.

    Удаляются ровно тексты комментариев-маркеров из токенов, поэтому строковые
    литералы с похожим содержимым не затрагиваются.
    """
    text = code.code
    markers = {
        token.value
        for index in range(code.token_count)
        if isinstance(token := code.get_token(index), Token) and is_value_marker_token(token)
    }
    for marker in markers:
        text = re.sub(rf"[ \t]*{re.escape(marker)}[ \t]*$", "", text, flags=re.MULTILINE)
    return text


def bind_value_annotations(registry: SituationRegistry) -> None:
    """Записать ``Action.annotation`` по всем маркерам кода."""
    code = registry.code
    for comment in code.ast.find_paths_by_type("comment"):
        node = code.ast.get(comment.id)
        content = str(node.get("content", "")) if node is not None else ""
        line = code.code_line_number_by_id(comment.id)
        prefix = f"строка {line}: " if line is not None else ""
        try:
            values = parse_value_marker(content)
        except ValueMarkerSyntaxError as error:
            raise ValueAnnotationError(
                f"{prefix}некорректная разметка {content.strip()}: {error}"
            ) from error
        if values is None:
            continue

        action = _annotated_condition(registry, comment)
        if action is None:
            raise ValueAnnotationError(
                f"{prefix}{content.strip()} — к комментарию не привязано условие"
            )
        if action.annotation is not None:
            raise ValueAnnotationError(
                f"{prefix}{content.strip()} — условие уже размечено на строке "
                f"{action.annotation.line}"
            )
        action.annotation = ValueAnnotation(
            values=tuple(item.value for item in values),
            hints=tuple(item.hint for item in values),
            marker=format_value_marker(values),
            line=line,
        )


def _annotated_condition(
    registry: SituationRegistry, comment: NodePathElement
) -> Action | None:
    """Условие конструкции, в заголовке которой лежит владелец комментария."""
    # Комментарий на своей строке - узел в statements, у него нет владельца.
    if comment.field_name != "trailing_comments" or comment.parent is None:
        return None

    owner = comment.parent
    path_ids: set[int] = set()
    current: NodePathElement | None = owner
    while current is not None:
        path_ids.add(current.id)
        construct = registry.get_construct_for(current.id)
        conditions = (
            [action for action in construct.actions if action.is_condition]
            if construct is not None
            else []
        )
        if conditions:
            if current is owner and current.type not in _TRAILING_CONDITION_TYPES:
                return None
            # У ветвления условие ветви лежит на пути к владельцу, у цикла оно одно
            # (у range-for оно привязано к переменной, а комментарий - к range.stop).
            on_path = [action for action in conditions if action.ast_id in path_ids]
            if len(on_path) == 1:
                return on_path[0]
            return conditions[0] if len(conditions) == 1 else None
        if current.field_name in _BODY_FIELDS:
            return None
        current = current.parent
    return None
