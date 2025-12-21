def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


x = 6
y = 7

while y % x != 0:
    y += 1

print(y)
print(gcd(x, y))

# Added comment for clarity
