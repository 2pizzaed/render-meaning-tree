from collections.abc import Iterable, Mapping


def bit(n: int) -> int:
    """Return 2**n for a non-negative, zero-based bit position."""
    return 1 << n


def pack_flags(flag_dict: Mapping[str, object], identifiers: Iterable[str]) -> int:
    """
    Объединяет через OR флаги идентификаторов из словаря любой вложенности.

    Флагами считаются только int-значения (без bool); группы и прочие значения
    игнорируются. Флаги повторяющихся имён объединяются через OR.
    Для неизвестных идентификаторов выводится предупреждение.
    """
    flags: dict[str, int] = {}
    pending: list[Mapping[str, object]] = [flag_dict]
    while pending:
        for name, value in pending.pop().items():
            if isinstance(value, int) and not isinstance(value, bool):
                flags[name] = flags.get(name, 0) | value
            elif isinstance(value, Mapping):
                pending.append(value)

    bitmask = 0
    for name in identifiers:
        val = flags.get(name)
        if val is not None:
            bitmask |= val
        else:
            print(f"Warning: Key '{name}' wasn't found in dictionary.")

    return bitmask
