a = 0
b = 0
x = 1364
while x > 0:
    y = x % 10
    if y > 3:
        a = a+1
    if y < 8:
        b = b+1
    x = x // 10
print(a)
print(b)