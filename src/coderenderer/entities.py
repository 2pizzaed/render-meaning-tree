from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.ast_managers import NodePathElement


class RendererEntity:
    pass


@dataclass
class Button(RendererEntity):
    type: str
    style: str
    attrs: dict[str, Any] = field(default_factory=dict)
    tooltip: str = ""
    css_style: str = ""
    color: str | None = "" # html color
    css_classes: list[str] = field(default_factory=list)


def make_button_attrs(action_id: int, node: "NodePathElement | None") -> dict[str, Any]:
    res: dict[str, int | str] = {
        "action-id": action_id,
    }
    if node:
        res |= {"node-id": node.id, "node-type": node.type}
    return {"attrs": res}


@dataclass
class Token(RendererEntity):
    _id: int
    value: str
    type: str
    index: int
    ast_node: "NodePathElement | None"
    css_classes: list[str] = field(default_factory=list) # custom классы, помимо основных
    color = ""

    def is_whitespace(self) -> bool:
        return self.type == "whitespace"

    def is_separator(self) -> bool:
        return self.type == "separator"

    def has_newline(self) -> int:
        return self.value.count("\n")
