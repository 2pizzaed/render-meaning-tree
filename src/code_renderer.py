
import os
from pathlib import Path
from typing import Any, ClassVar, Literal

from jinja2 import Environment, FileSystemLoader

from src.meaning_tree import node_hierarchy

ButtonType = Literal["play", "stop", "step-into", "step-out"]
ButtonStyle = Literal["filled", "outlined"]


class ASTNodeAnalyzer:
    """Анализатор узлов AST для определения типов кнопок"""

    def __init__(self, ast_tree: dict[str, Any], source_map: dict[str, Any]):
        self.ast_tree = ast_tree
        self.source_map = source_map
        self.nodes_cache = {}
        self.nodes_hierarchy_reference = node_hierarchy()
        self._build_nodes_cache()

    def _build_nodes_cache(self):
        """Построить кэш узлов по ID для быстрого доступа"""

        def traverse(node, prev=None):
            if isinstance(node, dict):
                if "id" in node:
                    self.nodes_cache[node["id"]] = node
                    self.nodes_cache[node["id"]].setdefault(
                        "parent",
                        prev.get("id") if prev else None)
                for value in node.values():
                    traverse(value, node)
            elif isinstance(node, list):
                for item in node:
                    traverse(item, prev)

        traverse(self.ast_tree.get("root_node", {}))

    def get_node_by_id(self, node_id: str | int) -> dict[str, Any] | None:
        """Получить узел по ID"""
        return self.nodes_cache.get(int(node_id))

    def get_node_type_by_id(self, node_id: str | int) -> str | Literal[""]:
        """Получить узел по ID"""
        node = self.get_node_by_id(node_id)
        if not node:
            return ""
        return node.get("type", "").lower()

    def is_compound_statement(self, node_id: int | None) -> bool:
        """Проверить, является ли узел составным statement (циклы, if), но не блоки и ветви условий"""
        if not node_id:
            return False

        compound_types = {
            "general_for_loop",
            "range_for_loop",
            "while_loop",
            "do_while_loop",
            "if_statement",
            "switch_statement",
        }

        return self.get_node_type_by_id(node_id) in compound_types

    def get_node_types_hierarchy(self, node_id: int) -> list[str]:
        node_type = self.get_node_type_by_id(node_id)
        node_parent_types = self.nodes_hierarchy_reference.get(node_type, [])
        node_parent_types.insert(0, node_type)
        return node_parent_types


    def is_function_call(self, node_id: int) -> bool:
        """Проверить, является ли узел вызовом функции"""
        node_types = self.get_node_types_hierarchy(node_id)
        return "function_call" in node_types

    def is_nested_call(self, node_id: int | None) -> bool:
        """Проверить, является ли вызов функции вложенным в выражение"""
        if not node_id:
            return False

        node = self.get_node_by_id(node_id)
        if not node:
            return False

        if not self.is_function_call(node_id):
            return False

        # Проверяем, есть ли родительский узел, который не является statement
        parent_id = node.get("parent")
        if not parent_id:
            return False

        parent = self.get_node_by_id(parent_id)
        if not parent:
            return False

        # Если родитель - statement, то вызов не вложенный
        return "statement" in self.get_node_types_hierarchy(parent_id)

    def is_simple_statement(self, node_id: int | None) -> bool:
        """Проверить, является ли узел - простой инструкцией"""
        if not node_id:
            return False
        node = self.get_node_by_id(node_id)
        if not node:
            return False
        return node.get("type", "").lower() in [
                "variable_declaration",
                "expression_statement",
                "empty_statement",
                "assignment_statement",
        ]

    def is_block(self, node_id: int | None) -> bool:
        """Проверить, является ли узел - блоком"""
        if not node_id:
            return False
        node = self.get_node_by_id(node_id)
        if not node:
            return False
        return node.get("type", "").lower() == "compound_statement"


    def is_loop_or_condition_header(self, node_id: int | None) -> bool:
        """Проверить, является ли узел заголовком цикла или условия"""
        if not node_id:
            return False
        node = self.get_node_by_id(node_id)
        if not node:
            return False

        node_types = self.nodes_hierarchy_reference.get(
            node.get("type", "").lower(), [])

        parent_id = node.get("parent")
        if not parent_id:
            return False

        parent = self.get_node_by_id(parent_id)
        if not parent:
            return False

        return "expression" in node_types and parent.get("type", "").lower() in {
            "if_statement",
            "condition_branch",
            "switch_statement",
            "general_for_loop",
            "range_for_loop",
            "while_loop",
            "do_while_loop",
        }


class CodeHighlightGenerator:
    """Генератор HTML с подсветкой синтаксиса и интерактивными кнопками"""

    TOKEN_TYPE_CLASSES: ClassVar[dict[str, str]] = {
        "operator": "token-operator",
        "const": "token-const",
        "callable_identifier": "token-callable",
        "identifier": "token-identifier",
        "keyword": "token-keyword",
        "comment": "token-comment",
        "cast": "token-cast",
        "opening_brace": "token-brace",
        "closing_brace": "token-brace",
        "subscript_opening_brace": "token-brace",
        "subscript_closing_brace": "token-brace",
        "call_opening_brace": "token-brace",
        "call_closing_brace": "token-brace",
        "compound_opening_brace": "token-brace",
        "compound_closing_brace": "token-brace",
        "initializer_list_opening_brace": "token-brace",
        "initializer_list_closing_brace": "token-brace",
        "statement_token": "token-statement",
        "separator": "token-separator",
        "comma": "token-comma",
        "unknown": "token-unknown",
    }

    def __init__(self, template_path: str = "templates/base_new.html"):

        self.template_path = template_path
        self.analyzer = None

        # Используем встроенный загрузчик шаблонов Jinja2
        template_dir, template_file = os.path.split(template_path)
        env = Environment(
            loader=FileSystemLoader(template_dir or "."),
            autoescape=False,
        )
        self.template = env.get_template(template_file)

    def _get_node_at_position(self, byte_pos: int, pos: Literal["start", "end"] = "start") -> int | None:
        """Получить иерархию ID узлов, начиная с самого вложенного,
        на заданной байтовой позиции"""
        if not self.analyzer:
            return None

        map_data = self.analyzer.source_map.get("map", {})

        candidates = []
        for node_id, positions in map_data.items():
            if isinstance(positions, list) and len(positions) == 2:
                start, offset = positions
                end = start + offset
                if start <= byte_pos < end:
                    candidates.append((int(node_id), start, offset))
        if candidates:
            # Узлы с наименьшим размером (самые вложенные) сначала
            candidates.sort(key=lambda x: x[2])
            if self.analyzer.get_node_type_by_id(candidates[-1][0]) == "program_entry_point":
                candidates.pop(-1) # Убираем самый большой (самый внешний, это всегда точка входа)
            if not candidates:
                return None
            if pos == "end":
                return max(
                    enumerate(candidates),
                    key=lambda i: abs(byte_pos - i[1][1]) + i[0],
                )[1][0]
            return min(enumerate(candidates), key=lambda i: abs(byte_pos - i[1][1]) - i[0])[1][0]

        return None

    def _determine_button_type(
        self,
        token: dict[str, Any],
        node_token_pos: Literal["start", "middle", "end"],
        node_id: int | None,
        button_position: Literal["start", "end"],  # 'start' или 'end'
    ) -> tuple[ButtonType | None, ButtonStyle]:
        """
        Определить тип кнопки и стиль для токена

        Returns:
            (button_type, button_style) или (None, 'filled') если кнопка не нужна
        """
        if not node_id or not self.analyzer:
            return None, "filled"

        # Проверяем, является ли узел составным statement
        is_block = self.analyzer.is_block(node_id)
        is_simple_statement = self.analyzer.is_simple_statement(node_id)
        is_compound_statement = self.analyzer.is_compound_statement(node_id)
        is_nested_call = self.analyzer.is_nested_call(node_id)
        is_header = self.analyzer.is_loop_or_condition_header(node_id)

        # Вложенный вызов функции
        if is_nested_call:
            if button_position == "start" and node_token_pos == "start":  # noqa: S105
                return "step-into", "filled"
            if button_position == "end" and node_token_pos == "end":  # noqa: S105
                return "step-out", "filled"

        # Простой statement
        if is_simple_statement and button_position == "start":
            return "play", "filled"

        # Сложные statements, но не блоки и ветви условий
        if is_compound_statement:
            if button_position == "start" and node_token_pos == "start":  # noqa: S105
                return "play", "filled"
            if button_position == "end" and node_token_pos == "start":  # noqa: S105
                return "stop", "filled"

        # Заголовки циклов и условий
        if is_header and button_position == "start":
            return "play", "filled"

        # Составные statements
        if is_block and token.get("value", "").strip():
            if button_position == "start" and node_token_pos == "start":  # noqa: S105
                return "play", "outlined"
            if button_position == "end" and node_token_pos == "end":  # noqa: S105
                return "stop", "outlined"

        # Обычные statements
        token_type = token.get("token_type", "")
        if token_type == "statement_token" and button_position == "start":  # noqa: S105
            return "play", "filled"

        return None, "filled"

    def _escape_html(self, text: str) -> str:
        """Экранировать HTML специальные символы"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _add_spacing_between_tokens(self, tokens: list[dict[str, Any]],
                                    buttons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Добавить пробелы между токенами"""
        if not tokens:
            return tokens

        result = []
        token_i = 0
        for i, token in enumerate(tokens):
            result.append(token)

            # Добавляем пробел после токена, если это не последний токен
            if i < len(tokens) - 1:
                # Проверяем, не является ли следующий токен пробелом
                next_token = tokens[i + 1]

                need_spacing = (
                    token.get("css_class") not in ["token-whitespace"]
                    and next_token.get("css_class")
                    not in [
                        "token-whitespace",
                        "token-separator",
                        "token-comma",
                    ]
                    and not token.get("type", "").endswith("opening_brace")
                    and not next_token.get("type", "").endswith("closing_brace")
                    and not (token.get("node_type", "").startswith("unary")
                             and token.get("value", "") != "not")
                )
                after_button = any(
                    token_i > 0 and (but["index"] == token_i) for but in buttons
                )
                before_button = any(
                    but["index"] == token_i + 1 for but in buttons)

                if need_spacing and not before_button:
                    # Добавляем пробел
                    result.append(
                        {
                            "value": " ",
                            "type": "whitespace",
                            "css_class": "token-whitespace",
                            "node_id": None,
                            "id": None,
                        },
                    )
            token_i += 1  # noqa: SIM113
        return result

    def _determine_node_token_position(
        self,
        node_id: int | None,
        byte_pos: int,
        token: dict[str, Any],
    ) -> Literal["start", "middle", "end"]:
        """Определить позицию токена внутри узла: начало, середина, конец"""
        if not node_id or not self.analyzer:
            return "middle"

        map_data = self.analyzer.source_map.get("map", {})
        positions = map_data.get(str(node_id))
        if not positions or len(positions) != 2:
            return "middle"

        start, offset = positions
        end = start + offset
        token_value = token.get("value", "")
        token_length = len(token_value.encode("utf-8"))
        tol = int(token_length * 0.5)

        if start - tol <= byte_pos <= start + tol:
            return "start"
        if end - tol <= byte_pos + token_length <= end + tol:
            return "end"
        return "middle"

    def generate_html(
        self,
        source_map: dict[str, Any],
        tokens: dict[str, Any],
        output_file: str | None = None,
    ) -> str:
        """
        Генерировать HTML с подсветкой синтаксиса

        Args:
            source_map: Карта исходного кода
            tokens: Список токенов
            ast_tree: AST дерево (опционально, для расширенного анализа)
            output_file: Путь для сохранения HTML

        Returns:
            HTML строка
        """
        # Инициализируем анализатор, если есть AST
        self.ast_tree = source_map.get("origin", {})
        self.analyzer = ASTNodeAnalyzer(self.ast_tree, source_map)
        self.source = source_map.get("source_code", "").encode("utf-8")

        self.language = source_map.get("language", "Unknown")
        self.token_list = tokens.get("items", [])

        lines_data = []
        current_byte_pos = 0
        current_line_tokens = []
        buttons_on_line = []

        for i, token in enumerate(self.token_list):
            token_value = token.get("value", "")
            token_type = token.get("token_type", "unknown")
            token_id = token.get("id")

            newlines_in_token = token_value == "\n"  # noqa: S105

            if newlines_in_token == 0:
                # Токен на текущей строке
                node_id = self._get_node_at_position(current_byte_pos, "start")
                node_type = self.analyzer.get_node_type_by_id(node_id) if node_id else ""
                css_class = self.TOKEN_TYPE_CLASSES.get(token_type, "token-unknown")
                token_pos = len(current_line_tokens)
                node_token_pos = self._determine_node_token_position(node_id, current_byte_pos, token)

                # Обработка псевдо-токенов
                if token.get("is_pseudo") and token.get("type") == "whitespace":
                    css_class = "token-whitespace"

                # Проверяем, нужна ли кнопка в начале токена
                button_type, button_style = self._determine_button_type(
                    token, node_token_pos, node_id,
                    "start",
                )

                if button_type and not any(
                    b["position"] == "before" and b["node_id"] == node_id
                    for b in buttons_on_line
                ):
                    buttons_on_line.append(
                        {
                            "type": button_type,
                            "style": button_style,
                            "node_id": node_id,
                            "node_type": node_type,
                            "position": "before",
                            "index": token_pos,
                        },
                    )

                # Проверяем, нужна ли кнопка в конце токена
                button_type, button_style = self._determine_button_type(
                    token, node_token_pos,
                    node_id,
                    "end",
                )

                if button_type and not any(
                    b["position"] == "after" and b["node_id"] == node_id for b in buttons_on_line
                ):
                    buttons_on_line.append(
                        {
                            "type": button_type,
                            "style": button_style,
                            "node_id": node_id,
                            "node_type": node_type,
                            "position": "after",
                            "index": token_pos,
                        },
                    )

                current_line_tokens.append(
                    {
                        "value": self._escape_html(token_value),
                        "type": token_type,
                        "css_class": css_class,
                        "node_id": node_id,
                        "node_type": node_type,
                        "id": token_id,
                        "index": token_pos,
                    },
                )

                current_byte_pos += len(token_value.encode("utf-8"))
                if i + 1 < len(self.token_list) and self.token_list[i + 1].get("type", "") == "whitespace":
                    continue
                while current_byte_pos < len(self.source) and \
                    self.source[current_byte_pos:current_byte_pos + 1].isspace():
                    current_byte_pos += 1
            else:
                # Добавляем пробелы между токенами перед сохранением строки
                spaced_tokens = self._add_spacing_between_tokens(
                    current_line_tokens,
                    buttons_on_line,
                )
                current_byte_pos += 1

                lines_data.append({"tokens": spaced_tokens, "buttons": buttons_on_line})
                current_line_tokens = []
                buttons_on_line = []

        # Добавляем последнюю строку
        if current_line_tokens or buttons_on_line:
            spaced_tokens = self._add_spacing_between_tokens(current_line_tokens, buttons_on_line)
            lines_data.append({"tokens": spaced_tokens, "buttons": buttons_on_line})

        if not lines_data:
            lines_data.append({"tokens": [], "buttons": []})

        # Генерируем HTML
        html = self.template.render(
            language=self.language, lines=lines_data, total_lines=len(lines_data),
            code_data=source_map["origin"],
        )

        if output_file:
            with Path(output_file).open("w", encoding="utf-8") as f:
                f.write(html)

        self.analyzer = None
        return html
