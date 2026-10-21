# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:  # <! FFFT >
        return a
    return gcd(b, a % b)  # <! (-, "gcd(18, 12)"), (-, "gcd(12, 6)"), (-, "gcd(6, 0)") >

a = 48
b = 18
result = gcd(a, b)  # <! (-, "gcd(48, 18)") >
print("gcd:", result)
