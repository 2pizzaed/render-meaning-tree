import json
import traceback
from typing import Sequence

from flask import Flask, render_template, request

# Импорты из вашего проекта
from src.ast_managers import CodeManager, manage_code
from src.coderenderer.entities import Button, RendererEntity, Token
from src.coderenderer.injections import ControlFlowButtons
from src.meaning_tree import convert, to_tokens

app = Flask(__name__)


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
    if isinstance(current, Token) and isinstance(nxt, Token) and \
        current.value in ('=',) and nxt.value in ("(", ")", "[", "]"):
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
                spacer = Token(_id=-1, value=" ", type="whitespace", index=-1, ast_node=None)
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
            "token_range": token_range or ['?', '?'],
            # Дебаг инфо (опционально)
            # "debug_info": str(raw_node)[:100],
        }
    return nodes_data


@app.route("/", methods=["GET", "POST"])
def index():
    code = ""
    language = "java"  # Значение по умолчанию для формы
    lines = []
    nodes_json = "{}"
    error = None

    if request.method == "POST":
        code = request.form.get("code", "")
        language = request.form.get("language")

        if not language:
            error = "No language specified"
        else:
            try:
                # 1. Токенизация
                tokens_list = to_tokens(language, code)
                if not tokens_list:
                    raise Exception("Failed to tokenize code (backend returned None)")

                # 2. Source Map
                source_map = convert(code, language, language, source_map=True)
                if not source_map or not isinstance(source_map, dict):
                    raise Exception("Failed to generate source map")

                # 3. Инициализация менеджера
                manager = manage_code(tokens_list, source_map)

                # 4. Инъекции
                manager.apply_injections(ControlFlowButtons)

                # 5. Получение потока
                stream = manager.last_processed or []
                spaced_stream = add_spacing_to_stream(stream)
                # 6. Группировка в строки
                lines = group_stream_into_lines(spaced_stream)

                # 7. Сериализация AST (передаем manager целиком)
                nodes_data = serialize_ast_nodes(manager)
                nodes_json = json.dumps(nodes_data)

            except Exception as e:
                # Логируем в консоль
                traceback.print_exc()
                # Передаем ошибку в шаблон, чтобы показать в UI, а не падать с 500
                error = f"{type(e).__name__}: {e!s}"

    return render_template(
        "playground.html",
        code=code,
        language=language,
        lines=lines,
        total_lines=len(lines),
        nodes_json=nodes_json,
        error=error,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
