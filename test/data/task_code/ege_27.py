numbers = [10, 15, 7, 22, 9, 13, 8, 19, 11, 6]
k = 3
max_sum = [float("-inf")] * k
max_sum[0] = 0

for x in numbers:
    new_max = list(max_sum)
    for j in range(k):
        new_max[(j + x) % k] = max(new_max[(j + x) % k], max_sum[j] + x)
    max_sum = new_max
print(max_sum[0])
