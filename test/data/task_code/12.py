for i in range(1, 4):
    for j in range(1, 4):
        if i * j > 4:
            break
        print(f"{i}{j}", end=" ")
print("Done")