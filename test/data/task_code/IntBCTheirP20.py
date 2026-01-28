a = 1
b = 2
c = 3

vals = [a, b, c]
result = sum(x for x in vals if vals.count(x) == 1)