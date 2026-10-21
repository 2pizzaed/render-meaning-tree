# Число способов подняться по лестнице через одну или две ступени: match задаёт базу рекурсии
def stairs(n):
    match n:
        case 0 | 1:  # <! FTT >
            return 1
        case _:
            return stairs(n - 1) + stairs(n - 2)  # <! stairs#1: (-, "stairs(1)") > <! stairs#2: (-, "stairs(0)") >

print(stairs(2))  # <! (-, "stairs(2)") >
