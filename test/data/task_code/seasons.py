month = 7
temp = 35
if month >= 3:
    if month <= 5:
        season = 1  # весна
        if temp > 20:
            anomaly = 1
        else:
            anomaly = 0
    else:
        if month <= 8:
            season = 2  # лето
            if temp > 30:
                anomaly = 1
            else:
                anomaly = 0
        else:
            if month <= 11:
                season = 3  # осень
                if temp > 15:
                    anomaly = 1
                else:
                    anomaly = 0
            else:
                season = 4  # зима
                anomaly = 0
else:
    season = 4  # зима
    if temp > 5:
        anomaly = 1
    else:
        anomaly = 0
print(season, anomaly)
