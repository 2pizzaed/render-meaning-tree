# Переворот списка
def reverse_list(lst):
    if len(lst) <= 1:
        return lst
    return reverse_list(lst[1:]) + [lst[0]]

items = [1, 2, 3, 4, 5]
result = reverse_list(items)
print("reversed:", result)
