str_ = "12xy34xy"
word = "xy"

out = ""
i = 0
while i < len(str_):
    if str_[i:i+len(word)] == word:
        out += word
        i += len(word)
    else:
        out += "+"
        i += 1
result = out