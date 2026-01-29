m = 12
p = 1
k = 0
while m > 8:
    k = k + 1
    if m % 2 == 0:
        p = p * 2
        m = m // 2
    else:
        p = p + m
        m = m - 3
print(k, m, p)
