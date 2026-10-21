# Минимум и максимум списка: функция возвращает два значения
def min_max(nums):
    if len(nums) == 1:  # <! FT >
        return nums[0], nums[0]
    lo, hi = min_max(nums[1:])  # <! (-, "min_max([2])") >
    if nums[0] < lo:  # <! F >
        lo = nums[0]
    if nums[0] > hi:  # <! T >
        hi = nums[0]
    return lo, hi

print(min_max([5, 2]))  # <! (-, "min_max([5, 2])") >
