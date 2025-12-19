# Возведение в степень
def power(base, exp):
    if exp == 0:
        return 1
    power_result = power(base, exp - 1)
    return base * power_result

result = power(2, 5)
print("2^5 =", result)
