from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.ast_managers import NodePathElement


class RendererEntity:
    pass


@dataclass
class Button(RendererEntity):
    type: str
    style: str
    attrs: dict[str, Any] = {}
    tooltip: str = ""
    css_style: str = ""
    css_classes: list[str] = []


@dataclass
class Token(RendererEntity):
    _id: int
    value: str
    type: str
    index: int
    ast_node: NodePathElement | None
    css_classes: list[str] = [] # custom классы, помимо основных

    def is_whitespace(self) -> bool:
        return self.type == "whitespace"

    def is_separator(self) -> bool:
        return self.type == "separator"

    def has_newline(self) -> int:
        return self.value.count("\n")
