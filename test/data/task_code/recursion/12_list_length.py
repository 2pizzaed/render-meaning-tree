# Длина списка рекурсивно
def list_length(lst):
    if lst == []:  # <! FFFT >
        return 0
    return 1 + list_length(lst[1:])  # <! (-, "list_length(['b', 'c'])"), (-, "list_length(['c'])"), (-, "list_length([])") >

items = ["a", "b", "c"]
result = list_length(items)  # <! (-, "list_length(['a', 'b', 'c'])") >
print("length:", result)
