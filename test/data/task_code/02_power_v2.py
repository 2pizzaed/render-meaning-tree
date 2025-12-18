# Возведение в степень
def power(base, exp):
    if exp == 0:
        return 1
    return base * power(base, exp - 1)

result = power(3, 3)
print("3^3 =", result)

