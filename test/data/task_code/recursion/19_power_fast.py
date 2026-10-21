# Быстрое возведение в степень
def power_fast(base, exp):
    if exp == 0:  # <! FFT >
        return 1
    if exp % 2 == 0:  # <! TF >
        half = power_fast(base, exp // 2)  # <! (-, "power_fast(3, 1)") >
        return half * half
    return base * power_fast(base, exp - 1)  # <! (-, "power_fast(3, 0)") >

base = 3
exp = 2
result = power_fast(base, exp)  # <! (-, "power_fast(3, 2)") >
print("power:", result)
