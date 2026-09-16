# Переворот строки
def reverse_str(s):
    if len(s) <= 1:
        return s
    return reverse_str(s[1:]) + s[0]

text = "hello"
result = reverse_str(text)
print("reverse('hello') =", result)
