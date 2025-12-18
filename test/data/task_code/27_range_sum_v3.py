# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:
        return 0
    return a + range_sum(a + 1, b)

result = range_sum(4, 9)
print("sum(4..9) =", result)

