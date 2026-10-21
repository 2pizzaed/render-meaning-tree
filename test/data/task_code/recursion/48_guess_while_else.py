# Угадывание числа за три попытки: break при успехе, else при неудаче
def guess(secret, tries):
    attempt = 1
    while attempt <= 3:  # <! TT >
        if tries[attempt - 1] == secret:  # <! FT >
            print("угадано с попытки", attempt)
            break
        attempt += 1
    else:
        print("попытки кончились")

guess(7, [3, 7, 9])  # <! (-, "guess(7, [3, 7, 9])") >
