from collections.abc import Iterable


def pack_flags(flag_dict: dict[str, int], identifiers: Iterable[str]) -> int:
    """
    Принимает словарь флагов и список идентификаторов.
    Возвращает целое число, являющееся побитовым OR всех найденных флагов.
    """
    bitmask = 0
    for name in identifiers:
        # Получаем значение бита.
        # Если такого ключа нет в словаре, get вернет None, и мы его пропустим.
        val = flag_dict.get(name)
        if val is not None:
            bitmask |= val
        else:
            print(f"Warning: Key '{name}' wasn't found in dictionary.")

    return bitmask
