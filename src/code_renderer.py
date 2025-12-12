
import hashlib
import math
import os
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from src.ast_analyzer import ASTNodeAnalyzer
from src.cfg.abstractions import AppearanceType
from src.cfg.cfg import CFG
from src.helpers.diff import make_str_diff

ButtonType = Literal["play", "stop", "step-into", "step-out", "question"]
ButtonStyle = Literal["filled", "outlined"]


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

    # Предопределенная палитра цветов для скобок
    COLOR_PALETTE: ClassVar[list[str]] = [
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

    TOKEN_ASTTYPE_COLORS: ClassVar[dict[str, str]] = {
        "type": "#9B59B6",
    }

    # Строго заданные цвета кнопок
    BUTTON_COLORS: ClassVar[dict[str, str]] = {
        "play": "#0A1048",
        "stop": "#0A1048",
        "step-into": "#0F629A",
        "step-out": "#73328D",
        "question": "#024936",
    }

    # Цвета кнопок по типам узла
    BUTTON_TYPES_COLORS: ClassVar[dict[str, str]] = {
        "assignment_statement": "#34495E",
        "expression_statement": "#34495E",
        "variable_declaration": "#34495E",
    }

    def __init__(self, template_path: os.PathLike | str = "templates/base.html"):

        self.template_path = template_path
        self.analyzer = None

        # Используем встроенный загрузчик шаблонов Jinja2
        template_dir, template_file = os.path.split(template_path)
        env = Environment(
            loader=FileSystemLoader(template_dir or "."),
            autoescape=False,
        )
        self.template = env.get_template(template_file)
        self._debug = False

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool):
        self._debug = value

    def _get_node_at_position(self, byte_pos: int, token: dict[str, Any],
                              pos: Literal["start", "end"] = "start") -> int | None:
        """Получить иерархию ID узлов, начиная с самого вложенного,
        на заданной байтовой позиции"""
        if not self.analyzer:
            return None

        map_data = self.analyzer.source_map.get("byte_positions", {})

        candidates = []
        for node_id, positions in map_data.items():
            if isinstance(positions, list) and len(positions) == 2:
                start, offset = positions
                end = start + offset
                detected_pos = self._determine_node_token_position(
                        int(node_id), byte_pos, token
                )
                accept = detected_pos in [pos, "single"]

                if start <= byte_pos < end and accept:
                    candidates.append((int(node_id), start, offset, detected_pos))
        if candidates:
            # Узлы с наименьшим размером (самые вложенные) сначала
            candidates.sort(key=lambda x: x[2])
            if self.analyzer.get_node_type_by_id(candidates[-1][0]) == "program_entry_point":
                candidates.pop(-1) # Убираем самый большой (самый внешний, это всегда точка входа)
            if not candidates:
                return None
            # берем наименее вложенный узел и ближе к нашей позиции
            if pos == "end":
                # Есть хотя бы один кандидат - одиночный токен с неразличимым концом и началом
                if any(x[3] == "single" for x in candidates):
                    return min(
                        enumerate(candidates),
                        key=lambda i: abs(byte_pos - i[1][2]) - i[0],
                    )[1][0]
                return max(
                    enumerate(candidates),
                    key=lambda i: abs(byte_pos - i[1][2]) + i[0],
                )[1][0]
            return min(enumerate(candidates), key=lambda i: abs(byte_pos - i[1][1]) - i[0])[1][0]

        return None

    def _determine_button_type(
        self,
        token: dict[str, Any],
        node_token_pos: Literal["start", "middle", "end"],
        node_id: int | None,
        button_position: Literal["start", "end"],  # 'start' или 'end'
        next_token: dict[str, Any] | None
    ) -> list[tuple[ButtonType | None, ButtonStyle]]:
        """Определить, нужна ли интерактивная кнопка в данной позиции токенов и если нужна, то какая

        :param token: текущий просматриваемый токен
        :type token: dict[str, Any]

        :param node_token_pos: Позиция токена в узле AST (в начале, середине или конце всех токенов этого узла AST)
        :type node_token_pos: Literal[&quot;start&quot;, &quot;middle&quot;, &quot;end&quot;]

        :param node_id: Текущий AST Node id
        :type node_id: int | None

        :param button_position: Проверяемая позиция для кнопки: до токена или после него
        :type button_position: Literal[&quot;start&quot;, &quot;end&quot;]

        :return: тип кнопки и её стиль
        :rtype: tuple[ButtonType | None, ButtonStyle]
        """
        if not node_id or not self.analyzer:
            return [(None, "filled")]

        if node_id in self.appearance and self.appearance[node_id] == "none":
            return [(None, "filled")]

        possible_buttons = []

        # Проверяем, является ли узел составным statement
        is_block = self.analyzer.is_block(node_id)
        is_simple_statement = self.analyzer.is_simple_statement(node_id)
        # is_compound_statement = self.analyzer.is_compound_statement(node_id)
        is_nested_call = self.analyzer.is_nested_call(node_id, False)
        is_function_call = self.analyzer.is_function_call(node_id)
        is_header = self.analyzer.is_loop_or_condition_header(node_id)
        for_component = self.analyzer.determine_for_loop_component(node_id)

        # Кнопки в циклах general for (должна быть кнопка на каждое действие)
        if for_component == "range" and button_position == "start":
            if node_token_pos == "start":
                self._range_for = [token.get("value", "")]
                possible_buttons.append(("question", "outlined"))
            if node_token_pos == "middle" and self.language != "python":
                if (
                    token.get("value", "") != ";"
                    and len(self._range_for)
                    and self._range_for[-1] == ";"
                ):
                    self._range_for.append("") # dummy token as marker of processed semicolon
                    possible_buttons.append(("question", "outlined"))
                self._range_for.append(token.get("value", ""))
            elif node_token_pos == "end":
                self._range_for = []

        # для других циклов for
        if for_component and for_component != "range" and button_position == "start":
            possible_buttons.append(("question", "outlined"))

        # Вложенный вызов функции
        if is_nested_call or is_function_call:
            if button_position == "start" and node_token_pos == "start":
                possible_buttons.append(("step-into", "filled"))
            if button_position == "end" and node_token_pos == "end":
                possible_buttons.append(("step-out", "filled"))

        # Простой statement
        if is_simple_statement and button_position == "start":
            possible_buttons.append(("play", "filled"))

        # Сложные statements, но не блоки и ветви условий - решено удалить
        '''
        if is_compound_statement:
            if button_position == "start" and node_token_pos == "start":
                return "play", "filled"
            if button_position == "end" and node_token_pos == "start":
                return "stop", "filled"
        '''

        # Заголовки циклов и условий
        if is_header and button_position == "end":
            possible_buttons.append(("question", "outlined"))

        # Составные statements
        if is_block and token.get("value", "").strip() and self.language != "python":
            if button_position == "start" and node_token_pos == "start":
                possible_buttons.append(("play", "outlined"))
            if button_position == "end" and node_token_pos == "end":
                possible_buttons.append(("stop", "outlined"))

        # Обычные statements
        token_type = token.get("token_type", "")
        if token_type == "statement_token" and button_position == "start":
            possible_buttons.append(("play", "filled"))

        allowed_types = {"step-into", "step-out"} # несколько кнопок может быть только при условии наличия вызова функций
        if possible_buttons:
            allowed_types.add(possible_buttons[0][0])
        return [item for item in possible_buttons if item[0] in allowed_types]

    def _generate_color_from_string(
        self, text: str | int,
    ) -> str:
        """
        Генерирует HSL цвет на основе хеша строки из общей палитры

        Args:
            text: Строка для генерации цвета

        Returns:
            CSS HSL цвет
        """
        text_str = str(text)
        # Вычисляем хеш и берем индекс по модулю длины палитры
        palette = self.COLOR_PALETTE

        hash_obj = hashlib.md5(text_str.encode("utf-8"))
        hash_int = int(hash_obj.hexdigest(), 16)
        color_index = hash_int % len(palette)
        return palette[color_index]

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
                node_types = []
                next_node_types = []
                if self.analyzer:
                    node_types = self.analyzer.nodes_hierarchy_reference.get(
                        token.get("node_type", "")
                    , [])
                    next_node_types = self.analyzer.nodes_hierarchy_reference.get(
                        next_token.get("node_type", ""), [],
                    )

                need_spacing = (
                    token.get("css_class") not in ["token-whitespace"]
                    and next_token.get("css_class")
                    not in [
                        "token-whitespace",
                        "token-separator",
                        "token-comma",
                    ]
                    and not (
                        token.get("type", "") == "operator"
                        and token.get("value", "") in [".", "::"]
                    )
                    and not (
                        next_token.get("type", "") == "operator"
                        and next_token.get("value") in [".", "::"]
                    )
                    and not token.get("type", "").endswith("opening_brace")
                    and not next_token.get("type", "").endswith("closing_brace")
                    and not (
                        token.get("css_class") in ["token-identifier", "token-callable"]
                        and next_token.get("type", "").endswith("opening_brace")
                    )
                    and all("unary" not in t for t in node_types)
                    and all("postfix" not in t for t in next_node_types)
                ) or (
                    (
                        token.get("css_class") == "token-separator"
                        and next_token.get("css_class") == "token-separator"
                    )
                    or token.get("value", "") == "not"
                )

                after_button = any(
                    token_i > 0 and (but["index"] == token_i) for but in buttons
                )
                before_button = any(
                    but["index"] == token_i + 1 and but["position"] == "before" for but in buttons)

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
    ) -> Literal["start", "middle", "end", "single"]:
        """Определить позицию токена внутри узла: начало, середина, конец
        Анализирует source map для заданного node_id и с некоторыми допущениями (погрешностью)
        определяет к какой позиции среди всех токенов этого узла относится текущий, переданный
        токен

        :return: Позиция токена в узле. Если она - single, то различить начало, середину и конец токенов узла невозможно
        :rtype: Literal["start", "middle", "end", "single"]
        """

        if not node_id or not self.analyzer:
            return "middle"

        map_data = self.analyzer.source_map.get("byte_positions", {})
        positions = map_data.get(str(node_id))
        if not positions or len(positions) != 2:
            return "middle"

        start, offset = positions
        end = start + offset

        token_value = token.get("value", "")
        token_length = len(token_value.encode("utf-8"))
        # fuzzy-подход к определению границ узла по байтовым позициям
        tol = math.ceil(token_length * 0.5)

        # Конец и начало узла по токену из одного символа неразличимы.
        # Например, у `if N:`, N имеет конец и начало одновременно
        if abs(abs(end - start) - token_length) <= tol:
            return "single"

        if start - tol <= byte_pos <= start + tol:
            return "start"
        if end - tol <= byte_pos <= end + tol:
            return "end"
        return "middle"

    def is_token_color_required(self, token: dict[str, Any]):
        if self.analyzer and (node_id := token.get("node_id")):
            node_types = self.analyzer.get_node_types_hierarchy(node_id)
            if any(node_type in self.TOKEN_ASTTYPE_COLORS for node_type in node_types):
                return True

        # токен должен быть разукрашен в цвет?
        return token.get("css_class", "") == "token-brace" and \
            token.get("value", "") in ["{", "}"]

    def load_appearance_profile(self, cfg: CFG):
        # загрузка логики появления кнопок из CFG
        self.appearance = {}
        for node in cfg.nodes.values():
            # Добавляем в appearance_status_map только узлы с wrapped_ast и appearance != NONE
            # Это предотвращает попадание узлов тела функции в вызовах, которые должны быть скрыты
            if node.metadata.wrapped_ast and node.appearance != AppearanceType.NONE:
                self.appearance[
                    node.metadata.wrapped_ast.ast_node.get("id", "")
                ] = node.appearance

    def _add_buttons_if_needed(
        self,
        token,
        next_token,
        token_pos,
        node_token_pos,
        node_id,
        node_type,
        position,  # "start" или "end"
        buttons_on_line,
        node_type_colors,
        node_colors,
        total_buttons,
    ):
        """Добавляет кнопку, если это необходимо."""
        if not node_id or not self.analyzer:
            return total_buttons

        button_position = "before" if position == "start" else "after"
        token_pos_check = ["start", "single"] if position == "start" else ["end", "single"]

        # Определяем тип кнопки
        pos_for_button = node_token_pos if node_token_pos != "single" else position
        buttons = self._determine_button_type(
            token, pos_for_button, node_id, position,
            next_token
        )

        for button_type, button_style in buttons:
            # Проверяем условия для добавления кнопки
            if not button_type or node_token_pos not in token_pos_check:
                continue

            # Проверяем, не добавлена ли уже такая кнопка
            button_exists = any(
                b["position"] == button_position
                and b["node_id"] == node_id
                and b["type"] == button_type
                and (position == "end" or node_type != "range")
                for b in buttons_on_line
            )

            if button_exists:
                continue

            # Добавляем кнопку
            buttons_on_line.append({
                "type": button_type,
                "style": button_style,
                "action_id": total_buttons,
                "node_id": node_id,
                "node_type": node_type,
                "atom": self.analyzer.is_simple_statement(node_id) or button_type == "question",
                "position": button_position,
                "index": token_pos,
                "color": self.BUTTON_TYPES_COLORS.get(node_type)
                or self.BUTTON_COLORS.get(button_type),
            })
            total_buttons += 1

        return total_buttons

    def prepare_interactive_data(
        self,
        source_map: dict[str, Any],
        tokens: dict[str, Any],
        appearance_status_map: dict[int, AppearanceType] = {}
    ) -> list[dict[str, list[Any]]]:
        """Подготовить данные для HTML генератора

        :param source_map: карта исходного кода из Meaning Tree
        :type source_map: dict[str, Any]
        :param tokens: все токены для переданного кода из Meaning Tree
        :type tokens: dict[str, Any]
        :param appearance_status_map: логика появления кнопок из CFG, по умолчанию - всё отображать
        :type appearance_status_map: dict[int, AppearanceType], optional
        :return: подготовленные для шаблонизатора HTML данные по токенам и кнопкам на каждой строке
        :rtype: list[dict[str, list[Any]]]
        """

        # Инициализируем анализатор, если есть AST
        self.ast_tree = source_map.get("origin", {})
        self.analyzer = ASTNodeAnalyzer(self.ast_tree, source_map)
        self.source = source_map.get("source_code", "").encode("utf-8")
        self.appearance = appearance_status_map

        self.language = source_map.get("language", "Unknown")
        self.token_list = tokens.get("items", [])

        # буфер цветов для каждого узла
        node_colors = {}  # {node_id: color}
        node_type_colors = {}  # {node_type: color}

        lines_data = []
        current_byte_pos = 0 # какой байт в исходной строке кода сейчас обрабатывается, позиция перед текущим токеном на каждом этапе
        current_line_tokens = []
        buttons_on_line = []
        total_buttons = 0

        for i, token in enumerate(self.token_list):
            token_value = token.get("value", "").rstrip("\r")
            token_type = token.get("token_type", "unknown")
            token_id = token.get("id")
            next_token = None
            if i + 1 < len(self.token_list):
                next_token = self.token_list[i + 1]

            newlines_in_token = token_value == "\n" or token_value == "\r\n"

            if newlines_in_token == 0:
                # Токен на текущей строке

                # Найдем, какой узел в начале токена
                node_start_id = self._get_node_at_position(current_byte_pos, token, "start")
                node_start_type = self.analyzer.get_node_type_by_id(node_start_id) if node_start_id else ""

                # Патч случаев, когда нам нужно изменить стартовый узел на его детей
                # (например, expression_statement на вложенный function_call)
                # нужно для корректного отображения кнопок захода и выхода из функции

                if node_start_type == "expression_statement" and self.analyzer and node_start_id:
                    node = self.analyzer.get_node_by_id(node_start_id)
                    if node:
                        child = node.get("expression", {})
                        child_id = child.get("id", 0)
                        if self.analyzer.is_function_call(
                            child_id
                        ):
                            node_start_id = child_id
                            node_start_type = child.get("type", "")

                css_class = self.TOKEN_TYPE_CLASSES.get(token_type, "token-unknown")
                token_pos = len(current_line_tokens)

                # Какое место в node по данной позиции токена: начало, середина, конец
                node_token_pos = self._determine_node_token_position(node_start_id, current_byte_pos, token)

                # Теперь узел для конца токена,
                node_end_id = self._get_node_at_position(
                    current_byte_pos + len(token_value.encode("utf-8")) - 1, token,
                    "end"
                )
                node_end_type = self.analyzer.get_node_type_by_id(node_end_id) if node_end_id else ""
                # Какое место в node в конце токена: начало, середина, конец
                node_token_end_pos = self._determine_node_token_position(
                    node_end_id, current_byte_pos + len(token_value.encode("utf-8")) - 1, token
                )

                # Патч случаев, когда нам нужно изменить стартовый узел на его детей
                # (например, expression_statement на вложенный function_call)
                # нужно для корректного отображения кнопок захода и выхода из функции

                if node_end_type == "expression_statement" and self.analyzer and node_end_id:
                    node = self.analyzer.get_node_by_id(node_end_id)
                    if node:
                        child = node.get("expression", {})
                        child_id = child.get("id", 0)
                        if self.analyzer.is_function_call(child_id):
                            node_end_id = child_id
                            node_end_type = child.get("type", "")

                # Обработка псевдо-токенов
                if token.get("is_pseudo") and token.get("type") == "whitespace":
                    css_class = "token-whitespace"

                # Генерируем цвета, если необходимо
                node_types = self.analyzer.get_node_types_hierarchy(node_start_id) \
                    if node_start_id else []
                color_type = list(filter(lambda x: x in self.TOKEN_ASTTYPE_COLORS, node_types))
                if color_type and node_start_id not in node_colors: # для токенов
                    color_type_name = next(iter(color_type))
                    node_colors[node_start_id] = self.TOKEN_ASTTYPE_COLORS[
                        color_type_name
                    ]
                if node_start_type not in node_type_colors: # для кнопок
                    node_type_colors[node_start_type] = self._generate_color_from_string(node_start_type)
                if node_start_id and node_start_id not in node_colors: # для токенов
                    node_colors[node_start_id] = self._generate_color_from_string(node_start_id)

                # Проверяем, нужна ли кнопка в начале токена
                total_buttons = self._add_buttons_if_needed(
                    token,
                    next_token,
                    token_pos,
                    node_token_pos,
                    node_start_id,
                    node_start_type,
                    "start",
                    buttons_on_line,
                    node_type_colors,
                    node_colors,
                    total_buttons,
                )

                # Проверяем, нужна ли кнопка в конце токена
                total_buttons = self._add_buttons_if_needed(
                    token,
                    next_token,
                    token_pos,
                    node_token_end_pos,
                    node_end_id,
                    node_end_type,
                    "end",
                    buttons_on_line,
                    node_type_colors,
                    node_colors,
                    total_buttons,
                )

                # формируем токен
                tok = {
                    "value": token_value.rstrip("\r\n"),
                    "type": token_type,
                    "css_class": css_class,
                    "node_id": node_start_id,
                    "node_type": node_start_type,
                    "id": token_id,
                    "index": token_pos,
                }
                if self.is_token_color_required(tok):
                    tok["color"] = node_colors.get(node_start_id) or node_colors.get(node_end_id)
                current_line_tokens.append(tok)


                # пропустить все пробельные символы и корректно учесть их в текущей байтовой позиции кода
                current_byte_pos += len(token_value.encode("utf-8"))
                # особое внимание к \r
                while (
                    current_byte_pos < len(self.source)
                    and self.source[current_byte_pos : current_byte_pos + 1] == b'\r'
                ):
                    current_byte_pos += 1
                if i + 1 < len(self.token_list) and self.token_list[i + 1].get("type", "") == "whitespace":
                    continue
                while current_byte_pos < len(self.source) and \
                    self.source[current_byte_pos:current_byte_pos + 1].isspace():
                    current_byte_pos += 1
            if token_value.endswith("\n"):
                # Добавляем пробелы между токенами перед сохранением строки
                spaced_tokens = self._add_spacing_between_tokens(
                    current_line_tokens,
                    buttons_on_line,
                )
                current_byte_pos += len(token_value.encode("utf-8"))
                if (
                    i + 1 < len(self.token_list)
                    and self.token_list[i + 1].get("type", "") != "whitespace"
                ):
                    while (
                        current_byte_pos < len(self.source)
                        and self.source[current_byte_pos : current_byte_pos + 1].isspace()
                    ):
                        if self.source[current_byte_pos : current_byte_pos + 1] == b'\n':
                            lines_data.append({"tokens": [], "buttons": []})
                        current_byte_pos += 1

                lines_data.append({"tokens": spaced_tokens, "buttons": buttons_on_line})
                current_line_tokens = []
                buttons_on_line = []

        # Добавляем последнюю строку
        if current_line_tokens or buttons_on_line:
            spaced_tokens = self._add_spacing_between_tokens(current_line_tokens, buttons_on_line)
            lines_data.append({"tokens": spaced_tokens, "buttons": buttons_on_line})

        # Предупреждение для потенциально неверной работы рендерера (что-то не отрисовалось из кода)
        if current_byte_pos < len(self.source):
            token_code = ""
            for line in lines_data:
                for token in line["tokens"]:
                    if token["id"]:
                        token_code += token["value"]
                token_code += "\n"
            diffs = make_str_diff(self.source.decode("utf-8"), token_code)
            print(f"Possible invalid html generation result, all tokens haven't been processed. See differences: {diffs}", file=sys.stderr)

        # если код пуст
        if not lines_data:
            lines_data.append({"tokens": [], "buttons": []})

        return lines_data


    def generate_html(self, lines_data: list[dict[str, list]],
                      source_map: dict[str, Any],
                      output_file: str | None = None) -> str:
        """Создать HTML из подготовленных данных

        :param lines_data: подготовленные данные из prepare_interactive_data
        :type lines_data: list[dict[str, list]]
        :param source_map: карта исходного кода
        :type source_map: dict[str, Any]
        :param snippet: выдать только html фрагмент с кодом (для production) или всю страницу html целиком
        :type snippet: bool, optional
        :param output_file: файл для вывода html
        :type output_file: str | None, optional

        :return: html код страницы или фрагмента с кодом (зависит от snippet)
        :rtype: str
        """
        # Генерируем HTML
        html = self.template.render(
            language=self.language, lines=lines_data, total_lines=len(lines_data),
            code_data=source_map["origin"], debug=self._debug
        )

        if not self._debug: # make only snippet in non-debug mode
            soup = BeautifulSoup(html, 'html.parser')
            code_block = soup.select_one(".ctrl-flow-domain-code-block")
            if code_block:
                html = code_block.decode(formatter="minimal")
            else:
                raise ValueError("Cannot find code block in generated HTML.")

        if output_file:
            with Path(output_file).open("w", encoding="utf-8") as f:
                f.write(html)

        self.analyzer = None
        return html
