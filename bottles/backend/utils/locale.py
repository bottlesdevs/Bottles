import locale
import subprocess


def available_locales() -> list:
    """
    List available locale names on host system
    """
    out = subprocess.run(['locale', '-a'], stdout=subprocess.PIPE).stdout.decode('utf-8')
    rv = out.rstrip('\n').splitlines()
    return rv


# noinspection PyTypeChecker
def sys_locale() -> tuple:
    return locale.getlocale()
