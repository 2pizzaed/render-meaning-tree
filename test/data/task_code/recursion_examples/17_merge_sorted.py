# Слияние двух отсортированных списков
def merge_sorted(a, b):
    if len(a) == 0:
        return b
    if len(b) == 0:
        return a
    if a[0] <= b[0]:
        return [a[0]] + merge_sorted(a[1:], b)
    return [b[0]] + merge_sorted(a, b[1:])

list1 = [1, 3, 5, 7]
list2 = [2, 4, 6, 8]
result = merge_sorted(list1, list2)
print("merged:", result)
