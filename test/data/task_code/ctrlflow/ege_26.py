n = 10
s = 100
pairs = [
    (5, 10), (15, 20), (8, 12),
    (10, 10), (6, 14)
]
pairs.sort()
count = 0
total = 0
for pair in pairs:
    a, b = pair
    if total + a + b <= s:
        total = total + a + b
        count = count + 1
print(count, s - total)
