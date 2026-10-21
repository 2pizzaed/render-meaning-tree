# Ханойские башни
def hanoi(n, src, dst, tmp):
    if n == 1:  # <! FTT >
        print("disk 1:", src, "->", dst)
        return
    hanoi(n - 1, src, tmp, dst)  # <! (-, "hanoi(1, 'A', 'B', 'C')") >
    print("disk", n, ":", src, "->", dst)
    hanoi(n - 1, tmp, dst, src)  # <! (-, "hanoi(1, 'B', 'C', 'A')") >

disks = 2
hanoi(disks, "A", "C", "B")  # <! (-, "hanoi(2, 'A', 'C', 'B')") >
