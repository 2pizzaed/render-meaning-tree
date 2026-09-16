# Копирование списка рекурсивно
def copy_list(lst):
    if len(lst) == 0:
        return []
    return [lst[0]] + copy_list(lst[1:])

original = [1, 2, 3]
copied = copy_list(original)
print("original:", original)
print("copy:", copied)
