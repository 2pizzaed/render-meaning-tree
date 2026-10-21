# Функция Аккермана
def ackermann(m, n):
    if m == 0:  # <! FFTT >
        return n + 1
    if n == 0:  # <! FT >
        return ackermann(m - 1, 1)  # <! (-, "ackermann(0, 1)") >
    return ackermann(m - 1, ackermann(m, n - 1))  # <! ackermann#1: (-, "ackermann(0, 2)") > <! ackermann#2: (-, "ackermann(1, 0)") >

m = 1
n = 1
result = ackermann(m, n)  # <! (-, "ackermann(1, 1)") >
print("ackermann:", result)
