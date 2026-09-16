# Проверка принадлежности элемента списку
def contains(lst, x):
    if len(lst) == 0:
        return False
    if lst[0] == x:
        return True
    return contains(lst[1:], x)

data = [10, 20, 30, 40]
found = contains(data, 30)
print("contains(30):", found)
