# Число путей в сетке вправо и вниз: два рекурсивных вызова в одном выражении
def paths(r, c):
    if r == 0 or c == 0:  # <! FTT >
        return 1
    return paths(r - 1, c) + paths(r, c - 1)  # <! paths#1: (-, "paths(0, 1)") > <! paths#2: (-, "paths(1, 0)") >

print(paths(1, 1))  # <! (-, "paths(1, 1)") >
