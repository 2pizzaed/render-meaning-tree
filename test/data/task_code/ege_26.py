n = 10
s = 100
pairs = [
    (5, 10), (15, 20), (8, 12), (3, 7), (25, 5),
    (10, 10), (6, 14), (18, 2), (9, 11), (4, 6)
]
pairs.sort()
count = 0
total = 0
for a, b in pairs:
    if total + a + b <= s:
        total = total + a + b
        count = count + 1
print(count, s - total)
