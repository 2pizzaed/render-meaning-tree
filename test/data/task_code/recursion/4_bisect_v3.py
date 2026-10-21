N = 23  # Искомое число

def guess_number(low, high):
    guess = (low + high) // 2 # Предположение — середина диапазона
    sign = (N - guess)
    if sign == 0:  # <! FT >
        return guess  # Найдено
    elif sign > 0:  # <! T >
        low = guess + 1 # Сужаем диапазон поиска вверх
    else:
        high = guess - 1 # Сужаем диапазон поиска вниз
    result = guess_number(low, high)  # <! (-, "guess_number(16, 30)") >
    return result

guess_number(0, 30)  # <! (-, "guess_number(0, 30)") >
