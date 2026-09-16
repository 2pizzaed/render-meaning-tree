# Количество цифр в числе
def count_digits(n):
    if n < 10:
        return 1
    return 1 + count_digits(n // 10)

num = 98765
result = count_digits(num)
print("count_digits(98765) =", result)
