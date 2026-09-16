# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:
        return a
    gcd_result = gcd(b, a % b)
    return gcd_result

result = gcd(36, 24)
print("gcd(36, 24) =", result)
