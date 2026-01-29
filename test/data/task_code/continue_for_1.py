data = [10, -5, 8, -3, 12, 6, -7, 9]
total = 0
for val in data:
    if val < 0:
        continue
    total = total + val
print(total)
