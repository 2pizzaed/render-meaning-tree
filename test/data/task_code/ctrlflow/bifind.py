array = [1,0,3,8,5,7,11]
a, b = 0, len(array)
item = 8
while a < b - 1:
    m = (a + b) // 2
    cond = item < array[m]
    if cond:
        b = m
    else:
        a = m
if array[a] == item:
    print(a)
else:
    print("не нашел")
