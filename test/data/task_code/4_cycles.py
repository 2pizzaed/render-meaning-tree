def even_transform(n):
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append(i * 3)
        else:
            out.append(i - 1)
    return out

data = even_transform(7)
print(data)  # [0, 1, 6, 3, 12, 5, 18]


def filter_large(values):
    res = []
    for v in values:
        if v > 5:
            res.append(v)
    return res


total = 0
for x in filter_large(data):
    if x % 9 == 0:
        total += x
    else:
        total -= 2

print(total)  # 14
