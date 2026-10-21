# Разглаживание списка на один уровень вложенности
def flatten(lst):
    if lst == []:  # <! FFT >
        return []
    if isinstance(lst[0], list):  # <! FT >
        return lst[0] + flatten(lst[1:])  # <! (-, "flatten([])") >
    return [lst[0]] + flatten(lst[1:])  # <! (-, "flatten([[2, 3]])") >

nested = [1, [2, 3]]
result = flatten(nested)  # <! (-, "flatten([1, [2, 3]])") >
print("flatten:", result)
