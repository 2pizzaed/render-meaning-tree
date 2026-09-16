matrix = [
    [5, 12, 8],
    [3, 20, 7],
    [18, 6, 14]
]
count = 0
for i in range(len(matrix)):
    for j in range(len(matrix[i])):
        if i == j:
            if matrix[i][j] > 10:
                count = count + matrix[i][j]
        else:
            if matrix[i][j] % 2 == 0:
                if matrix[i][j] > 5:
                    count = count + 1
print(count)
