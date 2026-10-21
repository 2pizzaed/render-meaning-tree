# Ханойские башни
def hanoi(n, src, dst, tmp):
    if n == 0:  # <! FTT >
        return
    hanoi(n - 1, src, tmp, dst)  # <! (-, "hanoi(0, 'A', 'B', 'C')") >
    print("disk", n, ":", src, "->", dst)
    hanoi(n - 1, tmp, dst, src)  # <! (-, "hanoi(0, 'B', 'C', 'A')") >

disks = 1
hanoi(disks, "A", "C", "B")  # <! (-, "hanoi(1, 'A', 'C', 'B')") >
