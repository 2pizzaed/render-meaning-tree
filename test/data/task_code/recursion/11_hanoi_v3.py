# Ханойские башни
def hanoi(n, src, dst, tmp):
    if n == 1:  # <! FTT >
        print("disk 1:", src, "->", dst)
    else:
        hanoi(n - 1, src, tmp, dst)  # <! (-, "hanoi(1, 'A', 'C', 'B')") >
        print("disk", n, ":", src, "->", dst)
        hanoi(n - 1, tmp, dst, src)  # <! (-, "hanoi(1, 'C', 'B', 'A')") >

disks = 2
hanoi(disks, "A", "B", "C")  # <! (-, "hanoi(2, 'A', 'B', 'C')") >
