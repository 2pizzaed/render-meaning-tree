# Эхо: печать до рекурсивного вызова и после возврата из него
def echo(n):
    if n == 0:  # <! FFT >
        return
    print("вход", n)
    echo(n - 1)  # <! (-, "echo(1)"), (-, "echo(0)") >
    print("выход", n)

depth = 2
echo(depth)  # <! (-, "echo(2)") >
