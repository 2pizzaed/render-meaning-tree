from __future__ import annotations
from typing import Any

from src.types import Node
from src.serializers.serializer import Serializer


class Renderer(Serializer):
    """Рендер узлов meaning-tree в json-форме.

    Пример использования:

    renderer = HtmlRenderer()

    @renderer.node(type="if")
    def if_stmt(node):
        return f"<h1>{node['condition']}</h1>"

    print(renderer.render({"type": "if", "condition": "True"}))
    """

    def __init__(self, indent_count: int = 4) -> None:
        super().__init__()
        self.indenter = Indenter(indent_count)

    def render(self, node: Node) -> Any:
        return self.serialize(node)


class Indenter:
    """
    Контекстный менеджер для управления отступами.

    Пример использования:

        indenter = Indenter(count=4)
        print(indenter.indent("Level 0"))
        with indenter:
            print(indenter.indent("Level 1"))
            with indenter:
                print(indenter.indent("Level 2"))
    """

    def __init__(self, count: int, fill_value: str = " ") -> None:
        """
        Инициализация Indenter.

        :param count: количество символов отступа на один уровень
        :param fill_value: символ, используемый для отступа
        """
        self._indent_level = 0
        self._count = count
        self._fill_value = fill_value

    def indent(self, s: str) -> str:
        """
        Возвращает строку с добавленным отступом.

        :param s: строка, к которой добавить отступ
        :return: строка с отступом
        """
        indentation = self._fill_value * (self._indent_level * self._count)
        return f"{indentation}{s}"

    def __enter__(self) -> Indenter:
        self._indent_level += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._indent_level = max(0, self._indent_level - 1)


class CodeBlock:
    """
    Сборщик строк кода, который автоматически применяет отступы.

    Использование:
        block = CodeBlock(r.indenter)
        block.add("line1")
        block.add("line2")
        return block.render()
    """

    def __init__(self, indenter: Indenter):
        """
        :param indenter: контекстный менеджер отступов
        """
        self.indenter = indenter
        self.lines = []

    def add(self, line_or_lines: str | list[str]) -> None:
        if isinstance(line_or_lines, str):
            line_or_lines = [line_or_lines]
        self.lines.extend(line_or_lines)

    def add_with_indent(self, line_or_lines: str | list[str]) -> None:
        if isinstance(line_or_lines, str):
            line_or_lines = [line_or_lines]
        # Применяем отступ ко всем строкам внутри блока
        with self.indenter:
            self.add([self.indenter.indent(line) for line in line_or_lines])
