# Бинарный поиск в отсортированном списке
def binary_search(lst, target, low, high):
    if low > high:  # <! FF >
        return -1
    mid = (low + high) // 2
    if lst[mid] == target:  # <! FT >
        return mid
    elif lst[mid] > target:  # <! F >
        return binary_search(lst, target, low, mid - 1)
    else:
        return binary_search(lst, target, mid + 1, high)  # <! (-, "binary_search([1, 3, 5, 7, 9], 7, 3, 4)") >

arr = [1, 3, 5, 7, 9]
target = 7
idx = binary_search(arr, target, 0, len(arr) - 1)  # <! (-, "binary_search([1, 3, 5, 7, 9], 7, 0, 4)") >
print("index:", idx)
