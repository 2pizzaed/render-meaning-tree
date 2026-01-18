N = 5  # Искомое число

def guess_number(low, high):
    guess = (low + high) // 2 # Предположение — середина диапазона
    sign = (N - guess)
    if sign == 0:
        return guess  # Найдено
    elif sign > 0:
        low = guess + 1 # Сужаем диапазон поиска вверх
    elif sign < 0:
        high = guess - 1 # Сужаем диапазон поиска вниз
    result = guess_number(low, high)
    return result

guess_number(0, 30)
