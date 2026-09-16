str_ = "zipXzap"

end = ""
i = 0
while i < len(str_):
    if i + 2 < len(str_) and str_[i] == "z" and str_[i+2] == "p":
        end += "zp"
        i += 3
    else:
        end += str_[i]
        i += 1
result = end