nums = [1, 2, 2]

total = 0
ignore = False
for x in nums:
    if x == 6:
        ignore = True
    if not ignore:
        total += x
    if x == 7 and ignore:
        ignore = False
result = total