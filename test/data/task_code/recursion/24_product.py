# Произведение элементов списка
def product(lst):
    if len(lst) == 0:  # <! FFFFT >
        return 1
    return lst[0] * product(lst[1:])  # <! (-, "product([3, 4, 5])"), (-, "product([4, 5])"), (-, "product([5])"), (-, "product([])") >

numbers = [2, 3, 4, 5]
result = product(numbers)  # <! (-, "product([2, 3, 4, 5])") >
print("product:", result)
