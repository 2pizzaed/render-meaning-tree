str_ = "abcbob"

for i in range(len(str_) - 2):
    if str_[i] == "b" and str_[i + 2] == "b":
        result = True
result = False