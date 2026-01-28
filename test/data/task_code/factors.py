x = 16
d = set([1])
k = 2
while k * k <= x:
    if x % k == 0:
        d.add(k)
        d.add(x // k)
    k += 1
d.add(x)
print(d)