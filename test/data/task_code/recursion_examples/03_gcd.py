# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)

result = gcd(48, 18)
print("gcd(48, 18) =", result)
