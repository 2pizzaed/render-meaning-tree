# Произведение элементов списка
def product(lst):
    if len(lst) == 0:
        return 1
    return lst[0] * product(lst[1:])

numbers = [3, 4, 5, 6]
result = product(numbers)
print("product([3,4,5,6]) =", result)

