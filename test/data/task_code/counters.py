data = [7, 14, 3, 21, 10, 5, 28, 12, 9, 18]
count_x = 0
count_y = 0
sum_z = 0
i = 0
while i < len(data):
    if data[i] % 7 == 0:
        if data[i] > 10:
            count_x = count_x + 1
            sum_z = sum_z + data[i]
        else:
            count_y = count_y + 1
        i = i + 1
    else:
        if data[i] % 3 == 0:
            sum_z = sum_z + data[i] // 3
            i = i + 2
        else:
            i = i + 1
print(count_x, count_y, sum_z)
