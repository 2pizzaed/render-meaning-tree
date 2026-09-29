"""Локализованные имена объектов промежуточного LOQI-представления.

Декоратор добавляет объектам метаданные ``<LANG>.localizedName`` и ``pronoun``.
Какие объекты получают имя и откуда берутся его части, определяет реестр
резолверов ``тип LOQI-объекта → функция``. Чтобы поддержать новый класс,
достаточно написать резолвер и добавить его в ``DEFAULT_NAME_RESOLVERS``.

Исходные значения берутся из сырых метаданных ``ConstructSpec``/``ActionSpec``
(``locale_trace_name``, ``locale_pronoun``, ``keyword``, ``identifier``), номер
строки и имя идентификатора — из кода. Атомарные inline-конструкты (``break``,
``continue``, ...) в представление не попадают, поэтому их метаданные ищутся по
объявлениям правил.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from html import escape
from typing import Any, cast

from src.ast_managers import CodeManager
from src.localization import MessageBundle
from src.model.rules import (
    ConstructDeclaration,
    Metadata,
    locate_construct_declaration_by_ast_node,
)
from src.serialization.loqi import (
    LoqiDecorator,
    LoqiMetadataEntry,
    LoqiObject,
    LoqiRenderIndex,
    LoqiRenderResult,
)
from src.types import Node

ON_LINE_KEY = "on_line"
TRACED_PREFIX_KEY = "traced_prefix"
TRACED_SUFFIX_KEY = "traced_suffix"


@dataclass(frozen=True, slots=True)
class NameMetadata:
    trace_name: str
    pronoun: str | None = None
    keyword: str | None = None
    identifier: bool = False

    @classmethod
    def from_spec(cls, spec: LoqiObject | None) -> NameMetadata | None:
        """Из сырых метаданных Spec-объекта представления."""
        if spec is None:
            return None
        value = LoqiRenderIndex.metadata_value
        trace_name = value(spec, "locale_trace_name")
        if not isinstance(trace_name, str) or not trace_name:
            return None
        pronoun = value(spec, "locale_pronoun")
        keyword = value(spec, "keyword")
        return cls(
            trace_name=trace_name,
            pronoun=pronoun if isinstance(pronoun, str) else None,
            keyword=keyword if isinstance(keyword, str) else None,
            identifier=value(spec, "identifier") is True,
        )

    @classmethod
    def from_metadata(cls, metadata: Metadata | None) -> NameMetadata | None:
        """Из метаданных объявления правила."""
        if metadata is None or not metadata.locale_trace_name:
            return None
        keyword = metadata.extra.get("keyword")
        return cls(
            trace_name=metadata.locale_trace_name,
            pronoun=metadata.locale_pronoun,
            keyword=keyword if isinstance(keyword, str) else None,
            identifier=metadata.extra.get("identifier") is True,
        )


@dataclass(frozen=True, slots=True)
class NameParts:
    """Всё, из чего собирается имя объекта; ключи приставок необязательны."""

    metadata: NameMetadata
    ast_id: int | None = None
    prefix_key: str | None = None
    suffix_key: str | None = None


class NamingContext:
    """Представление, код и правила, доступные резолверам."""

    def __init__(
        self,
        result: LoqiRenderResult,
        code: CodeManager | None = None,
        rules: Sequence[ConstructDeclaration] = (),
    ) -> None:
        self.index = LoqiRenderIndex(result)
        self.code = code
        self.rules = list(rules)
        self._constructs_by_ast_id = {
            ast_id: construct
            for construct in self.index.objects_of_type("ConcreteConstruct")
            if (ast_id := ast_id_of(construct)) is not None
        }
        # Поиск строки проходит по всем токенам, а одно действие встречается
        # в трассе многократно.
        self.line = cache(self._line)

    def construct_for(self, ast_id: int | None) -> LoqiObject | None:
        return self._constructs_by_ast_id.get(ast_id) if ast_id is not None else None

    def node(self, ast_id: int | None) -> Node | None:
        if self.code is None or ast_id is None:
            return None
        return self.code.get_node_by_id(ast_id)

    def identifier(self, ast_id: int | None) -> str | None:
        node = self.node(ast_id)
        name_node = _identifier_node(node) if node is not None else None
        if name_node is None or self.code is None:
            return None
        name = name_node.get("name")
        if isinstance(name, str) and name:
            return name
        name_id = name_node.get("id")
        return self.code.code_piece(name_id) if isinstance(name_id, int) else None

    def inline_rule(self, ast_id: int | None) -> ConstructDeclaration | None:
        node = self.node(ast_id)
        code = self.code
        if node is None or code is None or not self.rules:
            return None
        rule = locate_construct_declaration_by_ast_node(
            node,
            self.rules,
            type_matcher=lambda query, node_type: isinstance(node_id := query.get("id"), int)
            and code.ast.instanceof(node_id, node_type),
        )
        return rule if rule is not None and rule.is_atomic_inline else None

    def _line(self, ast_id: int | None) -> int | None:
        if self.code is None or ast_id is None:
            return None
        return self.code.code_line_number_by_id(ast_id)


type NameResolver = Callable[[LoqiObject, NamingContext], NameParts | None]


def resolve_construct(obj: LoqiObject, ctx: NamingContext) -> NameParts | None:
    metadata = NameMetadata.from_spec(ctx.index.target(obj, "derivedFrom"))
    return NameParts(metadata, ast_id_of(obj)) if metadata is not None else None


def resolve_action(obj: LoqiObject, ctx: NamingContext) -> NameParts | None:
    """
    Метаданные берутся целиком из одного источника, чтобы местоимение было
    согласовано с названием: собственный Spec → Spec конструкта с тем же
    ``ast_id`` → объявление атомарного inline-конструкта узла.
    """
    ast_id = ast_id_of(obj)
    metadata = NameMetadata.from_spec(ctx.index.target(obj, "derivedFrom"))
    if metadata is None and (construct := ctx.construct_for(ast_id)) is not None:
        metadata = NameMetadata.from_spec(ctx.index.target(construct, "derivedFrom"))
    if metadata is None and (inline_rule := ctx.inline_rule(ast_id)) is not None:
        metadata = NameMetadata.from_metadata(inline_rule.metadata)
    return NameParts(metadata, ast_id) if metadata is not None else None


def resolve_trace_act(obj: LoqiObject, ctx: NamingContext) -> NameParts | None:
    action = ctx.index.target(obj, "hasAction")
    parts = resolve_action(action, ctx) if action is not None else None
    if parts is None:
        return None
    return replace(parts, prefix_key=TRACED_PREFIX_KEY, suffix_key=TRACED_SUFFIX_KEY)


DEFAULT_NAME_RESOLVERS: Mapping[str, NameResolver] = {
    "ConcreteConstruct": resolve_construct,
    "ConcreteAction": resolve_action,
    "TraceAct": resolve_trace_act,
}


def localized_names_decorator(
    bundle: MessageBundle,
    code: CodeManager | None = None,
    rules: Sequence[ConstructDeclaration] = (),
    *,
    resolvers: Mapping[str, NameResolver] = DEFAULT_NAME_RESOLVERS,
    languages: tuple[str, ...] | None = None,
) -> LoqiDecorator:
    target_languages = languages if languages is not None else bundle.languages

    def decorate(result: LoqiRenderResult) -> None:
        ctx = NamingContext(result, code, rules)
        for obj in result.objects:
            resolver = resolvers.get(obj.type_name)
            parts = resolver(obj, ctx) if resolver is not None else None
            if parts is not None:
                obj.metadata.extend(localized_name_entries(parts, bundle, target_languages, ctx))

    return decorate


def localized_name_entries(
    parts: NameParts,
    bundle: MessageBundle,
    languages: tuple[str, ...],
    ctx: NamingContext,
) -> list[LoqiMetadataEntry]:
    line = ctx.line(parts.ast_id)
    identifier = ctx.identifier(parts.ast_id) if parts.metadata.identifier else None
    entries = [
        LoqiMetadataEntry(
            name=f"{lang.upper()}.localizedName",
            value=format_localized_name(parts, bundle, lang, line=line, identifier=identifier),
        )
        for lang in languages
    ]
    if parts.metadata.pronoun is not None:
        entries.append(LoqiMetadataEntry(name="pronoun", value=parts.metadata.pronoun))
    return entries


def format_localized_name(
    parts: NameParts,
    bundle: MessageBundle,
    lang: str,
    *,
    line: int | None = None,
    identifier: str | None = None,
) -> str:
    metadata = parts.metadata
    # Приставки есть не во всех языках: без фолбэка на язык по умолчанию.
    words = [_optional(bundle, parts.prefix_key, lang), bundle.translate(metadata.trace_name, lang)]
    if metadata.keyword:
        words.append(f"<code>{escape(bundle.translate(metadata.keyword, lang))}</code>")
    if identifier:
        words.append(f'<code class="id">{escape(identifier)}</code>')
    if line is not None:
        words.append(f"{bundle.translate(ON_LINE_KEY, lang)} {line}")
    words.append(_optional(bundle, parts.suffix_key, lang))
    return " ".join(word for word in words if word)


def ast_id_of(obj: LoqiObject) -> int | None:
    value = LoqiRenderIndex.property_value(obj, "ast_id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _optional(bundle: MessageBundle, key: str | None, lang: str) -> str | None:
    return bundle.get(key, lang) if key is not None else None


_IDENTIFIER_PATHS: dict[str, tuple[str, ...]] = {
    "function_definition": ("declaration", "name"),
    "method_definition": ("declaration", "name"),
    "function_call": ("function",),
    "method_call": ("method_name",),
}


def _identifier_node(node: Node) -> Node | None:
    current: Any = node
    for key in _IDENTIFIER_PATHS.get(str(node.get("type")), ()):
        current = current.get(key) if isinstance(current, dict) else None
    return cast(Node, current) if isinstance(current, dict) and current is not node else None


__all__ = [
    "DEFAULT_NAME_RESOLVERS",
    "NameMetadata",
    "NameParts",
    "NameResolver",
    "NamingContext",
    "format_localized_name",
    "localized_names_decorator",
    "resolve_action",
    "resolve_construct",
    "resolve_trace_act",
]
