# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:
        return 0
    return n + sum_to_n(n - 1)

result = sum_to_n(5)
print("sum(1..5) =", result)
