import pytest

from app.privacidade import ofuscar_nome


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("SEBASTIAO FERNANDO DE MELO", "SEBASTIAO F******* DE M***"),
        ("Elon Meira da Silva", "Elon M**** da S****"),
        ("  JOSE   AUGUSTO GOMES ", "JOSE A****** G****"),
        ("MARIA", "MARIA"),
        ("ANA E SILVA", "ANA E S****"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_ofuscar_nome(nome, esperado):
    assert ofuscar_nome(nome) == esperado
