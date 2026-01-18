# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:
        return a
    else:
        gcd_result = gcd(b, a % b)
        return gcd_result

result = gcd(60, 15)
print("gcd(60, 15) =", result)
