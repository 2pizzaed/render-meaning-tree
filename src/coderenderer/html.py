import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.ast_managers import CodeManager
from src.coderenderer.entities import Button, RendererEntity, Token
from src.coderenderer.injections import ControlFlowButtons


def should_add_space(current, nxt) -> bool:
    """
    Определяет, нужно ли вставлять пробел между текущим (current) и следующим (nxt) элементом.
    """
    # Не вставляем пробел, если один из токенов - кнопка (они сами имеют отступы)
    if isinstance(current, Button) or isinstance(nxt, Button):
        return False

    # Получаем текстовое значение токенов
    current_val = current.value if isinstance(current, Token) else ""
    next_val = nxt.value if isinstance(nxt, Token) else ""

    # 1. Не добавляем пробел, если текущий токен уже заканчивается пробелом или переносом строки.
    if current_val.endswith((" ", "\n", "\t")):
        return False

    # 2. Не добавляем пробел, если следующий токен начинается с пробела или переноса строки.
    if next_val.startswith((" ", "\n", "\t")):
        return False

    # 3. Не добавляем пробел перед определенными знаками препинания/операторами.
    #    Например, не нужно делать "func ()", "obj . method", "i ++"
    if (
        isinstance(current, Token)
        and isinstance(nxt, Token)
        and current.value in ("=",)
        and nxt.value in ("(", ")", "[", "]")
    ):
        return True

    if isinstance(nxt, Token) and nxt.value in ("(", ")", ";", ":", ",", ".", "[", "]", "++", "--"):
        return False

    # 4. Не добавляем пробел после открывающей скобки
    return not (isinstance(current, Token) and current.value in ("(", "["))


def add_spacing_to_stream(stream: Sequence[RendererEntity]) -> list:
    """
    Проходит по потоку RendererEntity и вставляет пробельные токены там, где это необходимо.
    """
    if not stream:
        return []

    new_stream = []
    for i, current_entity in enumerate(stream):
        # Сначала добавляем текущий элемент
        new_stream.append(current_entity)

        # Проверяем, нужно ли добавить пробел после него
        # (смотрим на следующий элемент)
        if i + 1 < len(stream):
            next_entity = stream[i + 1]
            if should_add_space(current_entity, next_entity):
                # Вставляем "фальшивый" токен-пробел
                spacer = Token(_id=-1, value=" ", type="whitespace", class_name="whitespace", index=-1, ast_node=None)
                new_stream.append(spacer)

    return new_stream


def group_stream_into_lines(stream):
    """
    Преобразует плоский поток Token и Button в список строк для рендеринга.
    Учитывает переносы строк внутри токенов.
    """
    lines = []
    current_line = []

    if not stream:
        return []

    for entity in stream:
        if isinstance(entity, Button):
            current_line.append(entity)
        elif isinstance(entity, Token):
            text = entity.value
            # Если в токене есть перенос строки (например, в строковом литерале или whitespace)
            if "\n" in text:
                parts = text.split("\n")
                for i, part in enumerate(parts):
                    # Если часть не пустая, создаем для нее "виртуальный" токен
                    if part:
                        sub_token = Token(
                            _id=entity._id,
                            value=part,
                            type=entity.type,
                            class_name=entity.class_name,
                            index=entity.index,
                            ast_node=entity.ast_node,
                            css_classes=entity.css_classes,
                        )
                        current_line.append(sub_token)

                    # Если это не последняя часть, значит здесь был \n -> закрываем строку
                    if i < len(parts) - 1:
                        lines.append(current_line)
                        current_line = []
            else:
                current_line.append(entity)

    # Добавляем хвост, даже если он пустой (важно для пустых строк в конце файла)
    lines.append(current_line)

    return lines


def extract_buttons_from_context(context: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Извлекает технические метаданные о кнопках из HTML-контекста.

    Возвращает список словарей с полями:
    - action_id: идентификатор действия (int | None)
    - node_id: идентификатор AST-узла (int | None)
    - node_type: тип AST-узла (str | None)
    - position: \"before\" / \"after\" относительно узла, если задано
    - type: тип кнопки (\"play\", \"question\", ...)
    - line_index, column_index: положение кнопки в потокe строк
    """
    lines: list[Sequence[RendererEntity]] = context.get("lines") or []  # type: ignore[assignment]
    buttons: list[dict[str, Any]] = []

    for line_index, line in enumerate(lines):
        for column_index, entity in enumerate(line):
            if isinstance(entity, Button):
                raw_attrs = entity.attrs or {}
                # В attrs мы храним вложенный словарь с реальными HTML-атрибутами
                attrs = raw_attrs.get("attrs", raw_attrs)

                buttons.append(
                    {
                        "action_id": attrs.get("action-id"),
                        "node_id": attrs.get("node-id"),
                        "node_type": attrs.get("node-type"),
                        "position": attrs.get("position"),
                        "type": entity.type,
                        "line_index": line_index,
                        "column_index": column_index,
                    }
                )

    return buttons


def serialize_ast_nodes(manager: CodeManager):
    """
    Создает словарь данных об AST для фронтенда.
    Теперь принимает manager, чтобы вычислять диапазоны токенов.
    """
    nodes_data = {}
    analyzer = manager.ast

    # analyzer итерируется по кешу (node_id, (path_elem, node_dict))
    for node_id, (path, raw_node) in analyzer._cache.items():
        parent_id = path.parent.id if path and path.parent else None

        # Получаем диапазон токенов (start, end) для подсветки в инспекторе
        token_range = manager.token_index_range(node_id)

        nodes_data[node_id] = {
            "id": node_id,
            "type": path.type if path else "unknown",
            "parent_id": parent_id,
            "field": path.field_name if path else None,
            # Индекс в массиве или ключ словаря (для Node Inspector)
            "collection_id": path.container_field_id if path else None,
            "token_range": token_range or ["?", "?"],
            # Дебаг инфо (опционально)
            # "debug_info": str(raw_node)[:100],
        }
    return nodes_data


def prepare_html_context(manager: CodeManager,
                         answer_objects: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Полный цикл обработки кода: от строки до контекста для шаблона.

    Args:
        manager: CodeManager, который уже обработал код и содержит AST и токены.
        answer_objects: Дополнительные объекты для отображения (например, результаты анализа)

    Returns:
        Словарь context для передачи в Jinja2 шаблон.
    """

    # Инъекции
    # В будущем здесь можно использовать cfg для фильтрации кнопок в ControlFlowButtons
    # Например: ControlFlowButtons.configure(cfg)
    manager.apply_injections(ControlFlowButtons)

    # Получение потока и форматирование
    stream = manager.last_processed or []
    spaced_stream = add_spacing_to_stream(stream)
    lines = group_stream_into_lines(spaced_stream)

    # Сериализация AST
    nodes_data = serialize_ast_nodes(manager)

    return {
        "code": manager.code,
        "language": manager.language,
        "lines": lines,
        "total_lines": len(lines),
        "nodes_json": json.dumps(nodes_data, ensure_ascii=False),
        "ast_json": json.dumps(manager.ast.root, indent=4, ensure_ascii=False),
        "answer_objects": answer_objects,
        "answer_objects_json": json.dumps(answer_objects, indent=4, ensure_ascii=False) if answer_objects else "",
        "debug": False,
    }


def render_static_html(
    context: dict[str, Any],
    template_name: str = "playground.html",
    component_template: str = "code_component.html",  # Имя шаблона только с кодом
    templates_dir: str = "templates",
    output_path: str | Path | None = None,
    snippet_only: bool = False,
    remove_snippet_styles: bool = True
) -> str:
    """
    Генерирует статический HTML на основе контекста данных.

    Args:
        context: Данные для рендеринга (результат CodeProcessingService.process)
        template_name: Имя основного шаблона (вся страница)
        component_template: Имя шаблона компонента (только код и стили)
        templates_dir: Путь к папке с шаблонами
        output_path: Если задано, сохраняет результат в файл
        snippet_only: Если True, рендерит только component_template (без head/body/скриптов)
    """
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    target_template_name = component_template if snippet_only else template_name

    try:
        template = env.get_template(target_template_name)
    except Exception as e:
        raise FileNotFoundError(
            f"Template '{target_template_name}' not found in directory '{templates_dir}'. "
            f"Details: {e}"
        )

    # Рендеринг
    updated_context = {**context,
                       "static_used": True,
                       "no_style_embed": remove_snippet_styles,
                       "snippet_mode": snippet_only
                       }
    html_content = template.render(**updated_context)

    # Сохранение в файл
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(html_content)

    return html_content
