x, s = 1, 0
while x < 10:
    s += x
    x += 1 if s % 3 else 2
    print(x, end=" ")
