# Возведение в степень
def power(base, exp):
    if exp == 0:
        return 1
    return base * power(base, exp - 1)

result = power(2, 5)
print("2^5 =", result)

