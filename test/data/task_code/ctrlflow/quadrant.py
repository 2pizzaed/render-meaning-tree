x = -3
y = 0
if x > 0:
    if y > 0:
        q = 1
    else:
        if y < 0:
            q = 4
        else:
            q = 0  # на оси
else:
    if x < 0:
        if y > 0:
            q = 2
        else:
            if y < 0:
                q = 3
            else:
                q = 0  # на оси
    else:
        q = 0  # начало координат
print(q)
