# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:  # <! FFT >
        return a
    gcd_result = gcd(b, a % b)  # <! (-, "gcd(24, 12)"), (-, "gcd(12, 0)") >
    return gcd_result

a = 36
b = 24
result = gcd(a, b)  # <! (-, "gcd(36, 24)") >
print("gcd:", result)
