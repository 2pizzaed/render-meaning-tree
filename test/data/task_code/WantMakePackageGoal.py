small = 4
big = 1
goal = 9

allbig = goal // 5
if allbig <= big:
    goal -= allbig * 5
else:
    goal -= big * 5

if goal <= small:
    result = goal
result = -1