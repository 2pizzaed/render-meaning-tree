str_ = "abcxyz"

for i in range(len(str_) - 2):
    if str_[i : i + 3] == "xyz" and (i == 0 or str_[i - 1] != "."):
        result = True
result = False