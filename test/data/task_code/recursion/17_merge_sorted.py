# Слияние двух отсортированных списков
def merge_sorted(a, b):
    if len(a) == 0:  # <! FFF >
        return b
    if len(b) == 0:  # <! FFT >
        return a
    if a[0] <= b[0]:  # <! TF >
        return [a[0]] + merge_sorted(a[1:], b)  # <! (-, "merge_sorted([4], [2])") >
    return [b[0]] + merge_sorted(a, b[1:])  # <! (-, "merge_sorted([4], [])") >

list1 = [1, 4]
list2 = [2]
result = merge_sorted(list1, list2)  # <! (-, "merge_sorted([1, 4], [2])") >
print("merged:", result)
