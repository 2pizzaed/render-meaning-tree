import os

IMAGE_EXT = [".png", ".jpg", ".jpeg", ".gif"]


def find_images(root_dir, keywords):
    results = []

    # Рекурсивный обход каталогов
    for current_dir, subdirs, files in os.walk(root_dir):
        # Перебираем каждый файл
        for filename in files:
            name_lower = filename.lower()
            filepath = os.path.join(current_dir, filename)

            # Проверяем расширение
            _, ext = os.path.splitext(name_lower)
            if ext not in IMAGE_EXT:
                continue

            # Проверяем наличие любого ключевого слова
            for kw in keywords:
                if kw in name_lower:
                    results.append(filepath)
                    break  # достаточно одного совпадения

    return results


if __name__ == "__main__":
    root = "C:/example/folder"
    keys = ["cat", "dog", "sunset"]

    found = find_images(root, keys)

    print("Найденные изображения:")
    for path in found:
        print(" -", path)
