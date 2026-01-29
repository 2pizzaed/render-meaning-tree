a = 1
b = 2
c = 3
d = 1

vals = [a, b, c, d]
s = 0
for x in vals:
    if vals.count(x) == 1:
        s += x
print(s)
