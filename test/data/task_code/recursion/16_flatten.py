# Разглаживание вложенного списка
def flatten(lst):
    if len(lst) == 0:
        return []
    first = lst[0]
    rest = flatten(lst[1:])
    if isinstance(first, list):
        return flatten(first) + rest
    return [first] + rest

nested = [1, [2, 3], [4, [5, 6]]]
result = flatten(nested)
print("flatten:", result)
