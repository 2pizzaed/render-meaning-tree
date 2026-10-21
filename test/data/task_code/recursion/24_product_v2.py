# Произведение элементов списка
def product(lst):
    if len(lst) == 0:  # <! FFFT >
        return 1
    product_result = product(lst[1:])  # <! (-, "product([2, 3])"), (-, "product([3])"), (-, "product([])") >
    return lst[0] * product_result

numbers = [1, 2, 3]
result = product(numbers)  # <! (-, "product([1, 2, 3])") >
print("product:", result)
