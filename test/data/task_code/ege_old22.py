x = 123
L = 0
M = 0
while x > 0:
    L += 1
    if x % 2 == 0:
        M = M + (x % 10) // 2
    x = x // 10
print(L)
print(M)
