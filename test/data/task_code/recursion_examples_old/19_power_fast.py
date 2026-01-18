# Быстрое возведение в степень
def power_fast(base, exp):
    if exp == 0:
        return 1
    if exp % 2 == 0:
        half = power_fast(base, exp // 2)
        return half * half
    return base * power_fast(base, exp - 1)

result = power_fast(2, 10)
print("2^10 =", result)
