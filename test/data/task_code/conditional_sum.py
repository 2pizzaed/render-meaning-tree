arr = [5, 12, 8, 15, 3, 20, 7, 18, 11, 6]
s = 0
for i in range(len(arr)):
    if i % 2 == 0:
        if arr[i] > 10:
            s = s + arr[i]
        else:
            s = s - arr[i]
    else:
        if arr[i] < 10:
            s = s + arr[i] * 2
print(s)
