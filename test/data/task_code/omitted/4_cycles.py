def even_transform(n):
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append(i * 3)
        else:
            out.append(i - 1)
    return out


def filter_large(values):
    res = []
    for v in values:
        if v > 5:
            res.append(v)
    return res


data = even_transform(7)

total = 0
for x in filter_large(data):
    if x % 3 == 0:
        total += x
    else:
        total -= 2

print(data)
print(total)
