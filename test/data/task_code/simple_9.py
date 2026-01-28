x = 0
for i in range(1, 5):
    y = i
    while y <= 2 * i:
        x = x + 1
        y = y + i
print(x)
