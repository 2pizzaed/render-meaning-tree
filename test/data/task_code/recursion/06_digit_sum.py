# Сумма цифр числа
def digit_sum(n):
    if n == 0:  # <! FFFT >
        return 0
    return n % 10 + digit_sum(n // 10)  # <! (-, "digit_sum(34)"), (-, "digit_sum(3)"), (-, "digit_sum(0)") >

num = 345
result = digit_sum(num)  # <! (-, "digit_sum(345)") >
print("digit sum:", result)
