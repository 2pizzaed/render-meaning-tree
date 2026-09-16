# Линейный поиск рекурсивно
def linear_search(lst, x, idx):
    if idx >= len(lst):
        return -1
    if lst[idx] == x:
        return idx
    return linear_search(lst, x, idx + 1)

data = [5, 3, 8, 1, 9, 2]
pos = linear_search(data, 9, 0)
print("position of 9:", pos)
