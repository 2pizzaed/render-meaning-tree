a = 7
b = 5
c = 0
for i in range(4):
    if a > b:
        c = c + a
        a = a - 2
    else:
        c = c + b
        b = b - 1
print(c)
