# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:
        return 0
    else:
        summ = sum_to_n(n - 1)
        return n + summ

result = sum_to_n(7)
print("sum(1..7) =", result)
