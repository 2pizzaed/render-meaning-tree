str_ = "aaacodebbb"

count = 0
for i in range(len(str_) - 3):
    if str_[i : i + 2] == "co" and str_[i + 3] == "e":
        count += 1
result = count
print(result)