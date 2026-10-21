str_ = "breadjambread"

first = str_.find("bread")
last = str_.rfind("bread")
if first == -1 or first == last:
    result = ""
result = str_[first + 5 : last]