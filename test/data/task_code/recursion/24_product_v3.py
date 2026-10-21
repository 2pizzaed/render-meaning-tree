# Произведение элементов списка
def product(lst):
    if len(lst) == 0:  # <! FFT >
        return 1
    else:
        product_result = product(lst[1:])  # <! (-, "product([4])"), (-, "product([])") >
        return lst[0] * product_result

numbers = [3, 4]
result = product(numbers)  # <! (-, "product([3, 4])") >
print("product:", result)
