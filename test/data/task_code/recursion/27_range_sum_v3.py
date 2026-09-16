# Сумма чисел в диапазоне
def range_sum(a, b):
    if a > b:
        return 0
    else:
        summ = range_sum(a + 1, b)
        return a + summ

result = range_sum(4, 9)
print("sum(4..9) =", result)
