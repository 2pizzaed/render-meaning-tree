# Поиск позиции элемента: else цикла сообщает, что элемента нет
def find_index(items, target):
    i = 0
    while i < len(items):  # <! TTF >
        if items[i] == target:  # <! FF >
            print("найден на позиции", i)
            break
        i += 1
    else:
        print("не найден")

numbers = [4, 7]
find_index(numbers, 9)  # <! (-, "find_index([4, 7], 9)") >
