# Сумма элементов списка
def list_sum(lst):
    if len(lst) == 0:  # <! FFFT >
        return 0
    return lst[0] + list_sum(lst[1:])  # <! (-, "list_sum([7, 2])"), (-, "list_sum([2])"), (-, "list_sum([])") >

numbers = [4, 7, 2]
result = list_sum(numbers)  # <! (-, "list_sum([4, 7, 2])") >
print("sum:", result)
