# Количество цифр в числе
def count_digits(n):
    if n < 10:  # <! FFFFT >
        return 1
    return 1 + count_digits(n // 10)  # <! (-, "count_digits(9876)"), (-, "count_digits(987)"), (-, "count_digits(98)"), (-, "count_digits(9)") >

num = 98765
result = count_digits(num)  # <! (-, "count_digits(98765)") >
print("digits:", result)
