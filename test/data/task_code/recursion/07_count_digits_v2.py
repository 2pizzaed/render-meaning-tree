# Количество цифр в числе
def count_digits(n):
    if n < 10:  # <! FFFT >
        return 1
    count = count_digits(n // 10)  # <! (-, "count_digits(123)"), (-, "count_digits(12)"), (-, "count_digits(1)") >
    return 1 + count

num = 1234
result = count_digits(num)  # <! (-, "count_digits(1234)") >
print("digits:", result)
