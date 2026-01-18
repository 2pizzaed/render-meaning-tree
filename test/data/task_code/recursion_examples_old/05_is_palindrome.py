# Проверка на палиндром
def is_palindrome(s):
    if len(s) <= 1:
        return True
    if s[0] != s[-1]:
        return False
    return is_palindrome(s[1:-1])

word = "radar"
result = is_palindrome(word)
print("is_palindrome('radar') =", result)
