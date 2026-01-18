# Сумма цифр числа
def digit_sum(n):
    if n == 0:
        return 0
    summ = digit_sum(n // 10)
    return n % 10 + summ

num = 9876
result = digit_sum(num)
print("digit_sum(9876) =", result)
