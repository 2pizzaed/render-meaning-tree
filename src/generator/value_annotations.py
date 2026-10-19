"""Ручная разметка значений комментарием ``<! … >``.

Маркер задаёт цепочку значений аннотируемого действия (``kind`` содержит
``annotated``) целиком (см. ``docs/ideas/value_annotations_idea.md``). Маркер со
значениями ``T``/``F`` стоит в заголовке цикла или ветви и размечает условие: привязка
идёт по дереву от узла, к которому MT прикрепил комментарий, вверх до ближайшей
конструкции с условием, не заходя в её тело. Маркер со значениями ``-`` размечает
BEGIN и END вызова функции на строке комментария внутри его владельца.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace

from src.ast_managers import CodeManager, NodePathElement
from src.coderenderer.entities import RendererEntity, Token
from src.generator.registry import SituationRegistry
from src.generator.value_marker import (
    ValueMarkerSyntaxError,
    format_value_marker,
    is_value_marker,
    parse_value_marker,
)
from src.model.situation import (
    Action,
    Construct,
    SemanticValue,
    TraceAct,
    ValueAnnotation,
)

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

        marker = content.strip()
        is_null = [item.value is None for item in values]
        if any(is_null) and not all(is_null):
            raise ValueAnnotationError(f"{prefix}{marker} — нельзя смешивать T/F и - в одной разметке")
        annotation = ValueAnnotation(
            values=tuple(item.value for item in values),
            hints=tuple(item.hint for item in values),
            marker=format_value_marker(values),
            line=line,
        )
        if all(is_null):
            calls = _annotated_calls(registry, comment, line)
            if len(calls) > 1:
                raise ValueAnnotationError(
                    f"{prefix}{marker} — на строке несколько вызовов функций, разметка неоднозначна"
                )
            targets = _call_annotations(calls[0], annotation) if calls else []
            missing, duplicate = "не привязан вызов функции", "вызов уже размечен"
        else:
            condition = _annotated_condition(registry, comment)
            targets = [(condition, annotation)] if condition is not None else []
            missing, duplicate = "не привязано условие", "условие уже размечено"
        if not targets:
            raise ValueAnnotationError(f"{prefix}{marker} — к комментарию {missing}")
        for action, action_annotation in targets:
            if action.annotation is not None:
                raise ValueAnnotationError(
                    f"{prefix}{marker} — {duplicate} на строке {action.annotation.line}"
                )
            action.annotation = action_annotation


def bind_call_end_hints(registry: SituationRegistry) -> None:
    """Подсказки значений END размеченных вызовов по трассе.

    BEGIN расходует цепочку в порядке входа в вызовы, END - в порядке выхода, поэтому
    подсказки END известны только по трассе: BEGIN- и END-акты одного вызова
    сопоставляются как скобки, и END-акт получает подсказку своего BEGIN.
    """
    open_begins: defaultdict[int, list[TraceAct]] = defaultdict(list)
    for act in registry.trace_acts:
        action = act.action
        if action.annotation is None or action.is_condition:
            continue
        opened = open_begins[action.parent.ast_id]
        if action.rule.role == "BEGIN":
            opened.append(act)
        elif action.rule.role == "END" and opened:
            begin = opened.pop()
            if isinstance(act.value, SemanticValue) and isinstance(begin.value, SemanticValue):
                act.value.hint_override = begin.value.hint_override


def _call_annotations(
    call: Construct, annotation: ValueAnnotation
) -> list[tuple[Action, ValueAnnotation]]:
    """Разметка BEGIN и END вызова.

    У END цепочка той же длины, но без подсказок: их по трассе расставляет
    ``bind_call_end_hints``. Значения ``null`` на переходы не влияют.
    """
    end_annotation = replace(annotation, hints=(None,) * len(annotation.hints))
    return [
        (action, end_annotation if action.rule.role == "END" else annotation)
        for action in call.actions
        if action.is_annotatable
    ]


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
            [
                action
                for action in construct.actions
                if action.is_condition and action.is_annotatable
            ]
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


def _annotated_calls(
    registry: SituationRegistry, comment: NodePathElement, line: int | None
) -> list[Construct]:
    """Размечаемые вызовы под владельцем комментария, занимающие строку комментария.

    Вызов - конструкт, у которого аннотируемые действия не условия (BEGIN и END
    вызова функции).
    """
    if comment.field_name != "trailing_comments" or comment.parent is None or line is None:
        return []
    owner = comment.parent
    code = registry.code
    # По узлу конструкта: BEGIN и END одного вызова дают одного кандидата.
    calls: dict[int, Construct] = {}
    for action in registry.all_actions():
        if not action.is_annotatable or action.is_condition:
            continue
        call = code.ast.get_path(action.parent.ast_id)
        lines = code.line_number_range(action.parent.ast_id)
        if call is None or lines is None:
            continue
        under_owner = call.id == owner.id or call.has_parent(owner.id)
        if under_owner and lines[0] <= line <= lines[1]:
            calls[action.parent.ast_id] = action.parent
    return list(calls.values())
