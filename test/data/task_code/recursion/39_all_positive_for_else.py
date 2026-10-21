# Все ли числа положительные: break прерывает цикл, и else не выполняется
def all_positive(nums):
    for x in nums:  # <! TT >
        if x <= 0:  # <! FT >
            print("нашлось", x)
            break
    else:
        print("все положительные")

values = [3, -1, 5]
all_positive(values)  # <! (-, "all_positive([3, -1, 5])") >
