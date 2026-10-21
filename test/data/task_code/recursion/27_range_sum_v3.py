# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:  # <! FFFT >
        return 0
    else:
        summ = range_sum(a + 1, b)  # <! (-, "range_sum(6, 7)"), (-, "range_sum(7, 7)"), (-, "range_sum(8, 7)") >
        return a + summ

a = 5
b = 7
result = range_sum(a, b)  # <! (-, "range_sum(5, 7)") >
print("sum:", result)
