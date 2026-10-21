
def fact(n):
    if n <= 1:  # <! FFFFT >
        return 1
    return n * fact(n - 1)  # <! (-, "fact(4)"), (-, "fact(3)"), (-, "fact(2)"), (-, "fact(1)") >

n = 5
y = fact(n)  # <! (-, "fact(5)") >
print("fact:", y)
