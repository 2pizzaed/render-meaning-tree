# Переворот строки
def reverse_str(s):
    if len(s) <= 1:  # <! FFFT >
        return s
    return reverse_str(s[1:]) + s[0]  # <! (-, "reverse_str('bcd')"), (-, "reverse_str('cd')"), (-, "reverse_str('d')") >

text = "abcd"
result = reverse_str(text)  # <! (-, "reverse_str('abcd')") >
print("reversed:", result)
