# Произведение элементов списка
def product(lst):
    if len(lst) == 0:
        return 1
    product_result = product(lst[1:])
    return lst[0] * product_result

numbers = [1, 2, 3]
result = product(numbers)
print("product([1,2,3]) =", result)
