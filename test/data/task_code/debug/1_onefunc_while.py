def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


x = int(input())
y = int(input())

while y % x != 0:
    y += 1

print(y)
print(gcd(x, y))

# Added comment for clarity
