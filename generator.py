import sys

if len(sys.argv) < 2:
    print("Ошибка: Не указан аргумент (имя файла или '-').", file=sys.stderr)
    sys.exit(1)

path = sys.argv[1]

try:
    if path == "-":
        content = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
except FileNotFoundError:
    print(f"Ошибка: Файл '{path}' не найден.", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    # Обработка других ошибок ввода-вывода
    print(f"Ошибка чтения '{path}': {e}", file=sys.stderr)
    sys.exit(1)


