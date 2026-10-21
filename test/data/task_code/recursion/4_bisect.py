N = 7  # Искомое число

def guess_number(low, high):
    guess = (low + high) // 2 # Предположение — середина диапазона
    sign = (N - guess)
    if sign == 0:  # <! FT >
        return guess  # Найдено
    elif sign > 0:  # <! F >
        low = guess + 1 # Сужаем диапазон поиска вверх
    elif sign < 0:  # <! T >
        high = guess - 1 # Сужаем диапазон поиска вниз
    return guess_number(low, high)  # <! (-, "guess_number(0, 14)") >

guess_number(0, 30)  # <! (-, "guess_number(0, 30)") >
