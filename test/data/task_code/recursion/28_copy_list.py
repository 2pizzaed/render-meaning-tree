# Копирование списка рекурсивно
def copy_list(lst):
    if len(lst) == 0:  # <! FFFT >
        return []
    return [lst[0]] + copy_list(lst[1:])  # <! (-, "copy_list([2, 3])"), (-, "copy_list([3])"), (-, "copy_list([])") >

original = [1, 2, 3]
copied = copy_list(original)  # <! (-, "copy_list([1, 2, 3])") >
print("copy:", copied)
