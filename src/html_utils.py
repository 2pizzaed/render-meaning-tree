import re
from collections.abc import Iterable

INDENT_STEP_PX = 25.7
INDENT_OFFSET_PX = 2.6


def add_indent_line(line: str, left_level: int = 0, left_px: float = INDENT_STEP_PX, left_offset_px: float = INDENT_OFFSET_PX) -> str:
    """ Adds to a line of text a span tag that shows vertical line for given level of indent. """
    left_style = f"left: {left_offset_px + left_level * left_px}px;"
    return f"<span class='indent-line' style='{left_style}'></span>{line}"


def add_indent_lines(
    lines: Iterable[str], left_level: int = 0, left_px: float = INDENT_STEP_PX,
) -> Iterable[str]:
    """
    Returns a generator that adds indent lines to all the given code lines.
    Args:
        lines: iterable of code lines
        left_level: not used (?!)
        left_px: inner constant
    """
    for line in lines:
        first_nonspace = -1
        for i, char in enumerate(line):
            if char != " ":
                first_nonspace = i
                break

        if first_nonspace != -1:
            left_level = (first_nonspace + 1) // 4

            for i in range(1, left_level + 1):
                line = add_indent_line(line, left_level=i, left_px=left_px)

        yield line


def syntax_highlight(
    lines: Iterable[str],
    keywords: Iterable[str] = ("if", "else", "for", "while"),
    special: str | Iterable[str] = "{}()=<>;+-/*",
    comment: Iterable[str] = ("//",),
    string: Iterable[str] = ('"', "'"),
    multiline_comments: Iterable[tuple[str, str]] = (("/*", "*/"),),
) -> Iterable[str]:
    """
    Универсальная подсветка синтаксиса для кода на разных языках.
    Данный код необходимо в будущем декомпозировать и переписать, но вряд ли
    это когда случится...
    """
    code = "\n".join(lines)

    # --- Ключевые слова ---
    if keywords:
        escaped_keywords = [re.escape(k) for k in keywords]
        keyword_regex = re.compile(r"\b(" + "|".join(escaped_keywords) + r")\b")
    else:
        keyword_regex = None

    # --- Спецсимволы ---
    special_chars = "".join(
        re.escape(c)
        for c in (special if not isinstance(special, str) else list(special))
    )
    special_regex = re.compile(r"([" + special_chars + r"])")

    # --- Игнорируемые блоки: строки, однострочные комментарии, многострочные комментарии ---
    ignore_patterns = []

    # Строковые литералы
    for q in string:
        ignore_patterns.append(
            rf"{re.escape(q)}(?:\\.|[^{re.escape(q)}\\])*{re.escape(q)}",
        )

    # Однострочные комментарии
    for c in comment:
        ignore_patterns.append(rf"{re.escape(c)}[^\n]*")

    # Многострочные комментарии
    for start, end in multiline_comments:
        ignore_patterns.append(rf"{re.escape(start)}[\s\S]*?{re.escape(end)}")

    # Общий паттерн
    pattern = re.compile("|".join(ignore_patterns), re.MULTILINE)

    result = []
    last_end = 0

    for match in pattern.finditer(code):
        # Код между игнорируемыми фрагментами
        segment = code[last_end : match.start()]
        if keyword_regex:
            segment = keyword_regex.sub(r'<span class="keyword">\1</span>', segment)
        segment = special_regex.sub(r'<span class="special">\1</span>', segment)
        result.append(segment)

        matched_text = match.group(0)
        if any(matched_text.startswith(c) for c in comment) or any(
            matched_text.startswith(s) for s, _ in multiline_comments
        ):
            result.append(f'<span class="comment">{matched_text}</span>')
        else:
            result.append(matched_text)

        last_end = match.end()

    # Остаток
    segment = code[last_end:]
    segment = special_regex.sub(r'<span class="special">\1</span>', segment)
    if keyword_regex:
        segment = keyword_regex.sub(r'<span class="keyword">\1</span>', segment)
    result.append(segment)

    return "".join(result).splitlines(keepends=True)
