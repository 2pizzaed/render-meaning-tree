a = 1
b = -5
c = 6
if a == 0:
    if b == 0:
        roots = 0  # нет решений
    else:
        roots = 1  # одно решение
else:
    d = b * b - 4 * a * c
    if d > 0:
        roots = 2
    else:
        if d == 0:
            roots = 1
        else:
            roots = 0
print(roots)
