# Количество цифр в числе
def count_digits(n):
    if n < 10:
        return 1
    count = count_digits(n // 10)
    return 1 + count

num = 123456
result = count_digits(num)
print("count_digits(123456) =", result)
