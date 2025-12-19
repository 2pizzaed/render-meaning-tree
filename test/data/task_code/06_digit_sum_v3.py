# Сумма цифр числа
def digit_sum(n):
    if n == 0:
        return 0
    summ = digit_sum(n // 10)
    return n % 10 + summ

num = 54321
result = digit_sum(num)
print("digit_sum(54321) =", result)
