
import hashlib

from src.coderenderer.entities import Token

BRACKET_COLOR_PALETTE: list[str] = [
    "#E74C3C",  # Красный
    "#3498DB",  # Синий
    "#9B59B6",  # Фиолетовый
    "#E67E22",  # Темно-оранжевый
    "#34495E",  # Темно-серый
    "#16A085",  # Темно-бирюзовый
    "#27AE60",  # Темно-зеленый
    "#2980B9",  # Темно-синий
    "#C0392B",  # Темно-красный
    "#2C3E50",  # Полночный синий
]


def palette_random_color(
    palette: list[str],
    text: str | int,
) -> str:
    """
    Генерирует HSL цвет на основе хеша строки из общей палитры

    Args:
        text: Строка для генерации цвета

    Returns:
        CSS HSL цвет
    """
    text_str = str(text)

    hash_obj = hashlib.md5(text_str.encode("utf-8"))
    hash_int = int(hash_obj.hexdigest(), 16)
    color_index = hash_int % len(palette)
    return palette[color_index]


def colorize_token(token: Token) -> Token:
    if token.ast_node and token.ast_node.instanceof("type"):
        token.css_classes.append("ast-type")
    if token.ast_node and token.is_separator() and token.value in "{}":
        token.color = palette_random_color(BRACKET_COLOR_PALETTE, token.ast_node.id)
    return token
