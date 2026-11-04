import pytest

from app.dinheiro import brl_para_centavos, centavos_para_brl, numero_para_centavos


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("6.659,92", 665992),
        ("R$ 6.659,92", 665992),
        ("R$       3.446,93", 344693),
        ("146,52", 14652),
        ("0,0", 0),
        ("R$ 0,00", 0),
        ("20.677,30", 2067730),
        ("-1,50", -150),
    ],
)
def test_brl_para_centavos(texto, esperado):
    assert brl_para_centavos(texto) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "6659.92", "1.23,45", "12,345"])
def test_brl_para_centavos_rejeita_formato_invalido(texto):
    with pytest.raises(ValueError):
        brl_para_centavos(texto)


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (103.3865, 10339),  # SEST/SENAT do RPA 13809297: planilha mostra 103,39
        (17.23465, 1723),
        (146.37216, 14637),
        (128.1852, 12819),
        (0, 0),
        (6653.28, 665328),
        ("29.2", 2920),
        (2.675, 268),  # float 2.675 é 2.67499999...; repr evita o erro binário
    ],
)
def test_numero_para_centavos_half_up(valor, esperado):
    assert numero_para_centavos(valor) == esperado


@pytest.mark.parametrize("valor", [None, "", "  ", "x", True])
def test_numero_para_centavos_rejeita_vazio_ou_invalido(valor):
    with pytest.raises(ValueError):
        numero_para_centavos(valor)


def test_centavos_para_brl():
    assert centavos_para_brl(2011902) == "R$ 20.119,02"
    assert centavos_para_brl(5) == "R$ 0,05"
    assert centavos_para_brl(-150) == "-R$ 1,50"
