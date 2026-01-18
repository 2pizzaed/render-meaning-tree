# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:
        return 0
    summ = sum_to_n(n - 1)
    return n + summ

result = sum_to_n(3)
print("sum(1..3) =", result)
