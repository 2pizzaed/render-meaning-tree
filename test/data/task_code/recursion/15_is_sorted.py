# Проверка на отсортированность
def is_sorted(lst):
    if len(lst) <= 1:  # <! FFF >
        return True
    if lst[0] > lst[1]:  # <! FFT >
        return False
    return is_sorted(lst[1:])  # <! (-, "is_sorted([2, 4, 3])"), (-, "is_sorted([4, 3])") >

numbers = [1, 2, 4, 3]
result = is_sorted(numbers)  # <! (-, "is_sorted([1, 2, 4, 3])") >
print("sorted:", result)
