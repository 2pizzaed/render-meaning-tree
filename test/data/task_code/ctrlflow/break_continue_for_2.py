matrix = [[2, 5], [3, 10], [7, 4]]
total = 0
for row in matrix:
    for val in row:
        if val > 8:
            break
        if val % 2 == 0:
            continue
        total = total + val
print(total)
