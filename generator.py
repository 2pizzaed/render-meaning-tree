import json
import sys
from pathlib import Path

from src.qgen_utils import build_question

debug = True

def detect_lang(path: str):
    match Path(path).suffix:
        case ".py":
            return "python"
        case ".c", ".cpp", ".hpp", ".h":
            return "c++"
        case ".java":
            return "java"


if len(sys.argv) < 2:
    print("Ошибка: Не указан аргумент (имя файла или '-').", file=sys.stderr)
    sys.exit(1)

path = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else detect_lang(path)

if not lang:
    print("Ошибка: Не обнаружен язык программирования, укажите его явно вторым аргументом")
    sys.exit(1)

try:
    if path == "-":
        content = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as f:
            content = f.read()
except FileNotFoundError:
    print(f"Ошибка: Файл '{path}' не найден.", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    # Обработка других ошибок ввода-вывода
    print(f"Ошибка чтения '{path}': {e}", file=sys.stderr)
    sys.exit(1)

q = build_question(lang,
                   content,
                   "debug_" + Path(path).name if debug and path != "-" else None)
print(json.dumps(q, indent=4))
