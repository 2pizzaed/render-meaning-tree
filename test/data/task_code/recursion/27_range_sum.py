# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:  # <! FFFT >
        return 0
    return a + range_sum(a + 1, b)  # <! (-, "range_sum(4, 5)"), (-, "range_sum(5, 5)"), (-, "range_sum(6, 5)") >

a = 3
b = 5
result = range_sum(a, b)  # <! (-, "range_sum(3, 5)") >
print("sum:", result)
