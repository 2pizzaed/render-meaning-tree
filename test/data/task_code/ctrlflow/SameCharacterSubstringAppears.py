str_ = "HelloHe"

if len(str_) < 2:
    result = str_
main_condition = str_[:2] == str_[-2:]
if main_condition:
    result = str_[2:]
result = str_