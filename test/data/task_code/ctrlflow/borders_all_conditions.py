a = 15
b = 0
for i in range(3):
    if a > 20:
        b = b + 10
    else:
        if a > 10:
            b = b + 5
            a = a + 8
        else:
            if a > 5:
                b = b + 3
                a = a - 2
            else:
                b = b + 1
print(a, b)
