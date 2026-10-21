# Проверка на палиндром
def is_palindrome(s):
    if len(s) <= 1:  # <! FFT >
        return True
    if s[0] != s[-1]:  # <! FF >
        return False
    return is_palindrome(s[1:-1])  # <! (-, "is_palindrome('ada')"), (-, "is_palindrome('d')") >

word = "radar"
result = is_palindrome(word)  # <! (-, "is_palindrome('radar')") >
print("palindrome:", result)
