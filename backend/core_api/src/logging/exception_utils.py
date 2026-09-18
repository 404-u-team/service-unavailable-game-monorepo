from typing import Dict


def into_dict(ex: Exception) -> Dict[str, str]:
    """
    Делает из ошибки словарь с именем исключения и содержимым
    """
    return {"exception_type": ex.__class__.__name__, "massage": str(ex)}


def named_error(name: str, message: str) -> BaseException:
    """
    Диначиски создает новое исключение с нужным названием и сообщением.
    Не использовать для обрабатываемых ошибок, только для быстрых прерываний и журналирования
    """
    cls = type(name, (BaseException,), {})
    exc = cls(message)
    return exc


def panic(err_name: str, msg: str):
    """
    Вызывает исключение с указанным именем и сообщением через named_error
    Только для быстрого прерывания и журналирования ошибок
    """
    raise named_error(err_name, msg)
