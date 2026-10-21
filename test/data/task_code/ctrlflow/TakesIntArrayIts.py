nums = [2, 1, 2, 3, 4]

s = 1
for x in nums:
    if x % 2 == 0:
        s += x
print(s)