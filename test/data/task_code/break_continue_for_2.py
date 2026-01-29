matrix = [[2, 5, 8], [3, 10, 6], [7, 4, 9]]
total = 0
for row in matrix:
    for val in row:
        if val > 8:
            break
        if val % 2 == 0:
            continue
        total = total + val
print(total)
