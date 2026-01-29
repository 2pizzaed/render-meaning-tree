data = [3, 7, 11, 5, 9, 13, 15, 6]
s = 0
limit = 30
for d in data:
    if d > 12:
        break
    if d % 2 == 0:
        continue
    s = s + d
    if s >= limit:
        break
print(s)
