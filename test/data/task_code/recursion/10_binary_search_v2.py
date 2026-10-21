# Бинарный поиск в отсортированном списке
def binary_search(lst, target, low, high):
    if low > high:  # <! FF >
        return -1
    mid = (low + high) // 2
    if lst[mid] == target:  # <! FT >
        return mid
    elif lst[mid] > target:  # <! T >
        index = binary_search(lst, target, low, mid - 1)  # <! (-, "binary_search([2, 4, 6, 8, 10], 2, 0, 1)") >
        return index
    else:
        index = binary_search(lst, target, mid + 1, high)
        return index

arr = [2, 4, 6, 8, 10]
target = 2
idx = binary_search(arr, target, 0, len(arr) - 1)  # <! (-, "binary_search([2, 4, 6, 8, 10], 2, 0, 4)") >
print("index:", idx)
