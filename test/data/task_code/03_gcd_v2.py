# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)

result = gcd(36, 24)
print("gcd(36, 24) =", result)

