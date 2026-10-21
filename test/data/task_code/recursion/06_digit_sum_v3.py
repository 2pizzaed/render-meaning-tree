# Сумма цифр числа
def digit_sum(n):
    if n == 0:  # <! FFFT >
        return 0
    else:
        summ = digit_sum(n // 10)  # <! (-, "digit_sum(50)"), (-, "digit_sum(5)"), (-, "digit_sum(0)") >
        return n % 10 + summ

num = 507
result = digit_sum(num)  # <! (-, "digit_sum(507)") >
print("digit sum:", result)
