
def fact(n):
    if n <= 1:  # <! FFFT >
        return 1
    factorial = fact(n - 1)  # <! (-, "fact(3)"), (-, "fact(2)"), (-, "fact(1)") >
    return n * factorial

n = 4
y = fact(n)  # <! (-, "fact(4)") >
print("fact:", y)
