import difflib

from colorama import Fore, Style, init

# Инициализация colorama для поддержки цветов в Windows
init(autoreset=True)


def make_str_diff(old: str, new: str) -> str:
    result: str = ""
    codes = difflib.SequenceMatcher(a=old, b=new).get_opcodes()
    for code in codes:
        if code[0] == "equal":
            result += Fore.WHITE + old[code[1] : code[2]]
        elif code[0] == "delete":
            result += Fore.RED + old[code[1] : code[2]]
        elif code[0] == "insert":
            result += Fore.GREEN + new[code[3] : code[4]]
        elif code[0] == "replace":
            result += Fore.RED + old[code[1] : code[2]] + Fore.GREEN + new[code[3] : code[4]]
    return result + Style.RESET_ALL
