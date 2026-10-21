score = 850
wins = 7
streak = 3
if score >= 1000:
    rank = 3
    bonus = 100
else:
    if score >= 500:
        rank = 2
        if wins > 5:
            if streak >= 3:
                bonus = 75
            else:
                bonus = 50
        else:
            bonus = 25
    else:
        rank = 1
        if wins > 3:
            bonus = 20
        else:
            bonus = 0
if streak >= 5:
    bonus = bonus + 30
final_score = score + bonus
print(rank, final_score)
