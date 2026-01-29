n = 4
total = 0
for i in range(1, n + 1):
    for j in range(1, n + 1):
        if i > j:
            if (i + j) % 2 == 0:
                total = total + i * j
            else:
                total = total + i + j
        else:
            if i == j:
                total = total + i
print(total)
