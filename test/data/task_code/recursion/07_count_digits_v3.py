# Количество цифр в числе
def count_digits(n):
    if n < 10:  # <! FFT >
        return 1
    else:
        count = count_digits(n // 10)  # <! (-, "count_digits(50)"), (-, "count_digits(5)") >
        return 1 + count

num = 506
result = count_digits(num)  # <! (-, "count_digits(506)") >
print("digits:", result)
