# Алгоритм Евклида (НОД)
def gcd(a, b):
    if b == 0:  # <! FFFT >
        return a
    else:
        gcd_result = gcd(b, a % b)  # <! (-, "gcd(15, 6)"), (-, "gcd(6, 3)"), (-, "gcd(3, 0)") >
        return gcd_result

a = 21
b = 15
result = gcd(a, b)  # <! (-, "gcd(21, 15)") >
print("gcd:", result)
