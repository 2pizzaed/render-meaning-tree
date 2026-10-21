# Линейный поиск рекурсивно
def linear_search(lst, x, idx):
    if idx >= len(lst):  # <! FFF >
        return -1
    if lst[idx] == x:  # <! FFT >
        return idx
    return linear_search(lst, x, idx + 1)  # <! (-, "linear_search([5, 3, 8, 1], 8, 1)"), (-, "linear_search([5, 3, 8, 1], 8, 2)") >

data = [5, 3, 8, 1]
x = 8
pos = linear_search(data, x, 0)  # <! (-, "linear_search([5, 3, 8, 1], 8, 0)") >
print("position:", pos)
