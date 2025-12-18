# Произведение элементов списка
def product(lst):
    if len(lst) == 0:
        return 1
    return lst[0] * product(lst[1:])

numbers = [1, 2, 3]
result = product(numbers)
print("product([1,2,3]) =", result)

