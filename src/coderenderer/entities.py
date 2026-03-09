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
    color: str | None = ""  # html color
    css_classes: list[str] = field(default_factory=list)


def make_button_attrs(
    action_id: int,
    node: "NodePathElement | None",
    position: str | None = None,
) -> dict[str, Any]:
    """
    Формирует словарь атрибутов для кнопки.

    Хранит технические данные в подсловаре ``attrs`` для использования как в HTML,
    так и в серверной части (генерация answerObjects и др.).
    """
    res: dict[str, int | str] = {
        "action-id": action_id,
    }
    if node:
        res |= {"node-id": node.id, "node-type": node.type}
    if position is not None:
        res["position"] = position  # "before" или "after" относительно связанного узла
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

    def is_brace(self) -> bool:
        return self.type.endswith("brace")

    def is_opening_brace(self) -> bool:
        return self.type.endswith("opening_brace")

    def is_closing_brace(self) -> bool:
        return self.type.endswith("closing_brace")

    def has_newline(self) -> int:
        return self.value.count("\n")
