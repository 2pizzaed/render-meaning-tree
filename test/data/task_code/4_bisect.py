def guess_number(low, high):  
    guess = (low + high) // 2 # Предположение — середина диапазона
    status = check_number(guess)
    if status == '=':
        return guess  # Найдено
    elif status == '<':
        low = guess + 1 # Сужаем диапазон поиска вверх
    elif status == '>':
        high = guess - 1 # Сужаем диапазон поиска вниз
    return guess_number(low, high)

guess_number(0, 10)
