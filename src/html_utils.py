from typing import Iterable


def add_indent_line(line: str, left_level: int = 0, left_px: int = 26.8) -> str:
    left_style = f"left: {left_level * left_px}px;"
    return f"<span class='indent-line' style='{left_style}'></span>{line}"


def add_indent_lines(
    lines: Iterable[str], left_level: int = 0, left_px: int = 26.8
) -> Iterable[str]:
    for line in lines:
        first_nonspace = -1
        for i, char in enumerate(line):
            if char != " ":
                first_nonspace = i
                break

        if first_nonspace != -1:
            left_level = (first_nonspace + 1) // 4

            for i in range(1, left_level + 1):
                line = add_indent_line(line, left_level=i)

        yield line
