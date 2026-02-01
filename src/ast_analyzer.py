from collections.abc import Generator
from typing import Any, Literal

from src.meaning_tree import node_hierarchy


class ASTNodeAnalyzer:
    """Анализатор узлов AST для определения типов кнопок"""

    def __init__(self, ast_tree: dict[str, Any], source_map: dict[str, Any]):
        """ ast_tree: AST in MeaningTree format """
        self.ast_tree = ast_tree
        self.source_map = source_map
        self.nodes_cache = {}
        self.user_defined_function_names = set()
        self.nodes_hierarchy_reference = node_hierarchy()
        self._build_nodes_cache()

    def get_code_piece_by_id(self, ast_id: int | str) -> str | None:
        source_code = self.source_map['source_code']
        byte_positions_for_id = self.source_map['byte_positions'].get(str(ast_id))
        if not byte_positions_for_id:
            return None
        start_byte, length = byte_positions_for_id
        # Конвертируем строку в байты, делаем срез, затем обратно в строку
        source_bytes = source_code.encode('utf-8')
        return source_bytes[start_byte:start_byte + length].decode('utf-8')

    def get_code_line_number_by_id(self, ast_id: int | str) -> int | None:
        """ 1-based line number for start position """
        source_code = self.source_map['source_code']
        byte_positions_for_id = self.source_map['byte_positions'].get(str(ast_id))
        if not byte_positions_for_id:
            return None
        start_byte, _length = byte_positions_for_id
        # Конвертируем строку в байты для корректного подсчёта
        source_bytes = source_code.encode('utf-8')
        return source_bytes[:start_byte].decode('utf-8').count('\n') + 1

    def _build_nodes_cache(self):
        """Построить кэш узлов по ID для быстрого доступа"""

        def traverse(node, prev=None, field=None):
            if isinstance(node, dict):
                if "id" in node:
                    self.nodes_cache[node["id"]] = node
                    self.nodes_cache[node["id"]].setdefault(
                        "parent", prev.get("id") if prev else None
                    )
                    self.nodes_cache[node["id"]].setdefault(
                        "parent_field",
                        field,
                    )
                if node.get("type", "") == "function_definition":
                    self.user_defined_function_names.add(
                        node.get("declaration", {}).get("name", "").get("name", "")
                    )
                for key, value in node.items():
                    traverse(value, node, key)
            elif isinstance(node, list):
                for item in node:
                    traverse(item, prev, field)

        traverse(self.ast_tree.get("root_node", self.ast_tree))

    def get_node_by_id(self, node_id: str | int) -> dict[str, Any] | None:
        """Получить узел по ID"""
        return self.nodes_cache.get(int(node_id))

    def node_nest_hierarchy(self, node_id: str | int) -> Generator[str] | None:
        """Получить иерархию вложенности узлов в дереве. Возвращает генератор типов узлов от непосредственного родителя к корню."""
        node = self.get_node_by_id(node_id)
        if not node:
            return None
        yield node.get("type", "")
        parent_id = node.get("parent")
        while parent_id:
            parent_node = self.get_node_by_id(parent_id)
            if not parent_node:
                break
            yield parent_node.get("type", "")
            parent_id = parent_node.get("parent")

    def find_children(self, node_id: str | int, max_depth: int = 1024) -> list[dict[str, Any]]:
        """Найти дочерние узлы для заданного узла по ID до указанной глубины"""
        result = []

        def traverse(current_id: str | int, depth: int):
            if depth > max_depth:
                return
            for child in self.nodes_cache.values():
                if child.get("parent") == current_id:
                    result.append(child)
                    traverse(child.get("id"), depth + 1)

        traverse(node_id, 1)
        return result

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
            # ??? >>>
            "program_entry_point",
        }

        return self.get_node_type_by_id(node_id) in compound_types

    def get_node_types_hierarchy(self, node_id: int) -> list[str]:
        """Получить иерархию наследования типов узла, т.е. например для method_call: [method_call, function_call, expression]"""
        node_type = self.get_node_type_by_id(node_id)
        node_parent_types = self.nodes_hierarchy_reference.get(node_type, [])
        node_parent_types.insert(0, node_type)
        return node_parent_types

    def instanceof(self, node_id: int, type: str):
        return type in self.get_node_types_hierarchy(node_id)

    def is_function_call(self, node_id: int) -> bool:
        """Проверить, является ли узел вызовом функции"""
        node_types = self.get_node_types_hierarchy(node_id)
        node = self.get_node_by_id(node_id)
        name = node.get("function", {}).get("name", "") if node else ""
        return "function_call" in node_types and name in self.user_defined_function_names

    def is_io_call(self, node_id: int) -> bool:
        """Проверить, является ли узел вызовом функции ввода/вывода"""
        node_types = self.get_node_types_hierarchy(node_id)
        return "print_command" in node_types or "print_command" in node_types

    def is_nested_call(self, node_id: int | None, include_io: bool = False) -> bool:
        """Проверить, является ли вызов функции вложенным в выражение"""
        if not node_id:
            return False

        node = self.get_node_by_id(node_id)
        if not node:
            return False

        # это вообще не вызов чего-либо
        if not self.is_function_call(node_id):
            return False

        if self.is_io_call(node_id) and not include_io:
            return False

        # Проверяем, есть ли родительский узел, который не является statement
        parent_id = node.get("parent")
        if not parent_id:
            return False

        parent = self.get_node_by_id(parent_id)
        if not parent:
            return False

        # Если родитель - expression_statement, то вызов не вложенный
        return "expression_statement" not in self.get_node_types_hierarchy(parent_id)

    def is_simple_statement(self, node_id: int | None) -> bool:
        """Проверить, является ли узел - простой инструкцией (statement) без вложенных в него блоков"""
        if not node_id:
            return False
        node = self.get_node_by_id(node_id)
        if not node:
            return False
        return node.get("type", "").lower() in [
            "variable_declaration",
            "expression_statement",
            "break_statement",
            "continue_statement",
            "return_statement",
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

    def determine_for_loop_component(self, node_id: int | None) -> str | None:
        """Определить, является ли узел компонентом цикла for (general, range-for)"""
        if not node_id:
            return None
        node = self.get_node_by_id(node_id)
        if not node:
            return None
        field = node.get("parent_field", "")

        nested = list(self.node_nest_hierarchy(node_id) or [])
        found_for_header = -1
        for i, parent in enumerate(nested):
            if parent in ["general_for_loop", "range_for_loop", "for_each_loop"]:
                found_for_header = i
                break
            if parent in ["compound_statement"]: # не заголовок цикла точно
                return None
        if found_for_header == -1:
            return None
        local_nested = nested[:found_for_header] # вложенность до непосредственного типа цикла
        for_type = nested[found_for_header]

        if node.get("type", "") == "identifier" and field not in ["container", "item", "identifier"]:
            return None

        if "range" in local_nested:
            return "range"

        if field == "body":
            return None

        return field

    def is_loop_or_condition_header(self, node_id: int | None) -> bool:
        """Проверить, является ли узел заголовком цикла или ветвления"""
        if not node_id:
            return False
        node = self.get_node_by_id(node_id)
        if not node:
            return False

        parent_id = node.get("parent")
        if not parent_id:
            return False

        parent = self.get_node_by_id(parent_id)
        if not parent:
            return False

        return node.get("parent_field", "") == "condition" and parent.get("type", "").lower() in {
            "if_statement",
            "condition_branch",
            "switch_statement",
            "general_for_loop",
            "range_for_loop",
            "while_loop",
            "do_while_loop",
        }
