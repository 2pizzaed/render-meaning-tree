nums = [1, 1, 1, 2, 1]

total = sum(nums)
left = 0
for i in range(len(nums) - 1):
    left += nums[i]
    if left == total - left:
        print(True)

