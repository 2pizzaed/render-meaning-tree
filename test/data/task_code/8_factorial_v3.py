
def fact(n):
    if n <= 1:
        return 1
    factorial = fact(n - 1)
    return n * factorial

y = fact(6)
print("fact(6) =", y)
