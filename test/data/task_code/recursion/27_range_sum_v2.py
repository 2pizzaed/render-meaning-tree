# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:  # <! FFFT >
        return 0
    summ = range_sum(a + 1, b)  # <! (-, "range_sum(3, 4)"), (-, "range_sum(4, 4)"), (-, "range_sum(5, 4)") >
    return a + summ

a = 2
b = 4
result = range_sum(a, b)  # <! (-, "range_sum(2, 4)") >
print("sum:", result)
