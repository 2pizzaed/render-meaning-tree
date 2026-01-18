# Поиск максимума в списке
def list_max(lst):
    if len(lst) == 1:
        return lst[0]
    rest_max = list_max(lst[1:])
    if lst[0] > rest_max:
        return lst[0]
    return rest_max

numbers = [3, 7, 2, 9, 1]
result = list_max(numbers)
print("list_max([3,7,2,9,1]) =", result)
