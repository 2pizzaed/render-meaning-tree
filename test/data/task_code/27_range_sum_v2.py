# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:
        return 0
    return a + range_sum(a + 1, b)

result = range_sum(2, 5)
print("sum(2..5) =", result)

