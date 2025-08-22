# file: iluflex_tools/core/protocols/validators.py
from __future__ import annotations


def get_safe_int(entrada: str, min: int, max: int, default: int) -> int:
    """Converte *entrada* para ``int`` e valida o intervalo; se falhar, retorna *default*.

    Regras:
      - Recorta espaços nas extremidades.
      - Converte via :func:`int` (aceita sinal e dígitos decimais padrão).
      - Se a conversão falhar ou o valor ficar fora de ``[min..max]``, retorna ``default``.
      - Não lança exceções.
      - Não normaliza limites (assume ``min <= max``).
    """


    s = (entrada or "").strip()
    if not s:
        return default
    try:
        value = int(s)
    except Exception:
        return default
    if value < min or value > max:
        return default
    return value


__all__ = ["get_safe_int"]   # diz para import o que importar no caso de import *

"""    
Exemplos (doctest):
    >>> get_safe_int("42", 0, 100, 9)
    42
    >>> get_safe_int("  -5 ", -10, 10, 0)
    -5
    >>> get_safe_int("abc", 0, 100, 9)
    9
    >>> get_safe_int("999", 0, 100, 9)
    9
    >>> get_safe_int("", 1, 9, 5)
    5
 """