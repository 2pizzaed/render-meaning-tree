# Сумма цифр числа
def digit_sum(n):
    if n == 0:
        return 0
    return n % 10 + digit_sum(n // 10)

num = 12345
result = digit_sum(num)
print("digit_sum(12345) =", result)
