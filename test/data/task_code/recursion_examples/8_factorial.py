
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

y = fact(5)
print("fact(5) =", y)
