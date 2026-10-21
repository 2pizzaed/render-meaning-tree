# Проверка принадлежности элемента списку
def contains(lst, x):
    if len(lst) == 0:  # <! FFF >
        return False
    if lst[0] == x:  # <! FFT >
        return True
    return contains(lst[1:], x)  # <! (-, "contains([20, 30, 40], 30)"), (-, "contains([30, 40], 30)") >

data = [10, 20, 30, 40]
x = 30
found = contains(data, x)  # <! (-, "contains([10, 20, 30, 40], 30)") >
print("found:", found)
