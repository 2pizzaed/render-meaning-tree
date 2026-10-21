# Подсчёт вхождений элемента в списке
def count_occurrences(lst, x):
    if len(lst) == 0:  # <! FFFT >
        return 0
    count = 1 if lst[0] == x else 0
    return count + count_occurrences(lst[1:], x)  # <! (-, "count_occurrences([1, 2], 2)"), (-, "count_occurrences([2], 2)"), (-, "count_occurrences([], 2)") >

data = [2, 1, 2]
x = 2
result = count_occurrences(data, x)  # <! (-, "count_occurrences([2, 1, 2], 2)") >
print("count:", result)
