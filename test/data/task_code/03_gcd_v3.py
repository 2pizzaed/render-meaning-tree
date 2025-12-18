# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)

result = gcd(60, 15)
print("gcd(60, 15) =", result)

