"""Valores monetários sempre em centavos (int) — nunca float na comparação."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_BRL = re.compile(r"^\s*(?:R\$\s*)?(-?)(\d{1,3}(?:\.\d{3})+|\d+),(\d{1,2})\s*$")


def brl_para_centavos(texto: str) -> int:
    """'R$ 6.659,92' -> 665992 ; '0,0' -> 0. Levanta ValueError se o formato não for BRL."""
    m = _BRL.match(texto)
    if not m:
        raise ValueError(f"valor monetário inválido: {texto!r}")
    sinal, inteiro, decimais = m.groups()
    valor = int(inteiro.replace(".", "")) * 100 + int(decimais.ljust(2, "0"))
    return -valor if sinal else valor


def numero_para_centavos(valor: object) -> int:
    """Valor numérico da planilha -> centavos, com ROUND_HALF_UP (igual à exibição #,##0.00 do Excel)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError("valor vazio")
    if isinstance(valor, bool):
        raise ValueError(f"valor numérico inválido: {valor!r}")
    try:
        d = Decimal(repr(float(valor))) if isinstance(valor, float) else Decimal(str(valor).strip())
    except InvalidOperation as e:
        raise ValueError(f"valor numérico inválido: {valor!r}") from e
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def centavos_para_brl(centavos: int) -> str:
    """2011902 -> 'R$ 20.119,02'"""
    sinal = "-" if centavos < 0 else ""
    inteiro, dec = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{dec:02d}"
