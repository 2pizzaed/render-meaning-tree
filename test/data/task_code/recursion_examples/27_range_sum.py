# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:
        return 0
    return a + range_sum(a + 1, b)

result = range_sum(3, 7)
print("sum(3..7) =", result)
