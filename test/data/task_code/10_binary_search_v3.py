# Бинарный поиск в отсортированном списке
def binary_search(lst, target, low, high):
    if low > high:
        return -1
    mid = (low + high) // 2
    if lst[mid] == target:
        return mid
    elif lst[mid] > target:
        return binary_search(lst, target, low, mid - 1)
    else:
        return binary_search(lst, target, mid + 1, high)

arr = [1, 3, 5, 7, 9, 11, 13]
idx = binary_search(arr, 11, 0, len(arr) - 1)
print("index of 11:", idx)

