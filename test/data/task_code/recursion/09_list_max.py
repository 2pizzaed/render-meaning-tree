# Поиск максимума в списке
def list_max(lst):
    if len(lst) == 1:  # <! FFT >
        return lst[0]
    rest_max = list_max(lst[1:])  # <! (-, "list_max([9, 5])"), (-, "list_max([5])") >
    if lst[0] > rest_max:  # <! TF >
        return lst[0]
    return rest_max

numbers = [3, 9, 5]
result = list_max(numbers)  # <! (-, "list_max([3, 9, 5])") >
print("max:", result)
