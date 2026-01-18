# Подсчёт вхождений элемента в списке
def count_occurrences(lst, x):
    if len(lst) == 0:
        return 0
    count = 1 if lst[0] == x else 0
    return count + count_occurrences(lst[1:], x)

data = [1, 2, 1, 3, 1, 4, 1]
result = count_occurrences(data, 1)
print("count of 1:", result)
