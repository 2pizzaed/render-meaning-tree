# Бинарный поиск в отсортированном списке
def binary_search(lst, target, low, high):
    if low > high:  # <! FF >
        return -1
    else:
        mid = (low + high) // 2
        if lst[mid] == target:  # <! FT >
            return mid
        elif lst[mid] > target:  # <! F >
            index = binary_search(lst, target, low, mid - 1)
            return index
        else:
            index = binary_search(lst, target, mid + 1, high)  # <! (-, "binary_search([1, 3, 5, 7, 9, 11], 9, 3, 5)") >
            return index

arr = [1, 3, 5, 7, 9, 11]
target = 9
idx = binary_search(arr, target, 0, len(arr) - 1)  # <! (-, "binary_search([1, 3, 5, 7, 9, 11], 9, 0, 5)") >
print("index:", idx)
