# Переворот списка
def reverse_list(lst):
    if len(lst) <= 1:  # <! FFFT >
        return lst
    return reverse_list(lst[1:]) + [lst[0]]  # <! (-, "reverse_list([2, 3, 4])"), (-, "reverse_list([3, 4])"), (-, "reverse_list([4])") >

items = [1, 2, 3, 4]
result = reverse_list(items)  # <! (-, "reverse_list([1, 2, 3, 4])") >
print("reversed:", result)
