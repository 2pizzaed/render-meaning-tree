# Длина списка рекурсивно
def list_length(lst):
    if lst == []:
        return 0
    return 1 + list_length(lst[1:])

items = ['a', 'b', 'c', 'd']
result = list_length(items)
print("length:", result)
