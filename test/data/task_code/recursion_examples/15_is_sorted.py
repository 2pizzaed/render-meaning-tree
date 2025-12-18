# Проверка на отсортированность
def is_sorted(lst):
    if len(lst) <= 1:
        return True
    if lst[0] > lst[1]:
        return False
    return is_sorted(lst[1:])

arr1 = [1, 2, 3, 4, 5]
arr2 = [1, 3, 2, 4, 5]
print("is_sorted([1,2,3,4,5]):", is_sorted(arr1))
print("is_sorted([1,3,2,4,5]):", is_sorted(arr2))
