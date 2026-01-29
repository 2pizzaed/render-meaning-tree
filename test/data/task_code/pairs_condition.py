data = [3, 7, 12, 5, 9, 15, 8, 11, 6, 14]
pairs = 0
for i in range(len(data)):
    for j in range(i + 1, len(data)):
        if data[i] + data[j] > 20:
            if data[i] % 2 == 0:
                if data[j] % 2 == 0:
                    pairs = pairs + 2
                else:
                    pairs = pairs + 1
print(pairs)
