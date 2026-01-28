nums = [1, 7, 7]

for i in range(len(nums) - 1):
    if nums[i] == 7 and nums[i + 1] == 7:
        result = True
for i in range(len(nums) - 2):
    if nums[i] == 7 and nums[i + 2] == 7:
        result = True
result = False