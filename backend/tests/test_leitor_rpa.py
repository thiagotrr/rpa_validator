from datetime import date

import pytest

from app.extracao.leitor_rpa import ErroLeituraRpa, interpretar_rpa, numero_rpa_do_arquivo
from tests.fixtures import textos_rpa as t


def _parse(texto, arquivo="RPA - FULANO - 13915419.doc"):
    return interpretar_rpa(texto, arquivo=arquivo, competencia="2026-10", metodo="nativo")


def test_layout_a_irrf_em_branco_vira_zero():
    r = _parse(t.A_IRRF_BRANCO)
    assert (r.valor_bruto, r.inss, r.irrf, r.sest_senat) == (665992, 14652, 0, 3330)
    assert r.data_emissao == date(2026, 10, 20)
    assert r.data_nascimento == date(1985, 4, 5)
    assert r.campos_ausentes == ()
    assert r.numero_rpa == "13915419"


def test_layout_a_inss_colado_ao_rotulo():
    r = _parse(t.A_INSS_COLADO)
    assert (r.inss, r.irrf, r.sest_senat) == (5386, 0, 3330)
    assert r.data_emissao == date(2026, 10, 24)


def test_layout_a_zero_com_uma_casa():
    r = _parse(t.A_ZERO_CURTO)
    assert (r.valor_bruto, r.inss, r.irrf, r.sest_senat) == (584320, 12855, 0, 2922)


def test_layout_b_rotulos_em_linhas():
    r = _parse(t.B_LINHAS, arquivo="RPA-Fulano - 14070887.doc")
    assert (r.valor_bruto, r.inss, r.irrf, r.sest_senat) == (344693, 7583, 0, 1723)
    assert r.data_emissao == date(2026, 10, 26)
    assert r.data_nascimento == date(1985, 11, 10)


def test_emissao_cai_para_data_do_rodape():
    r = _parse(t.SEM_EMISSAO)
    assert r.data_emissao == date(2026, 10, 20)
    assert "data_emissao" not in r.campos_ausentes


def test_texto_ilegivel_lista_campos_ausentes():
    r = _parse(t.ILEGIVEL)
    assert set(r.campos_ausentes) == {"valor_bruto", "inss", "irrf", "sest_senat", "data_emissao", "data_nascimento"}
    assert r.inss is None


def test_texto_com_acentos_removidos_por_ocr():
    r = _parse(t.B_LINHAS.replace("Emissão", "Emissao").replace("SEST/ SENAT", "SEST/SENAT"))
    assert r.sest_senat == 1723
    assert r.data_emissao == date(2026, 10, 26)


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("RPA - ELON MEIRA - 14101817.doc", "14101817"),
        ("RPA SEBASTIÃO FERNANDO -14103647.doc", "14103647"),
        ("RPA ELON  13765791.doc", "13765791"),
        ("ELON MEIRA - 13915419.doc", "13915419"),
        ("RPA-Marcos Antonio - 14070887.docx", "14070887"),
        ("C:\\Users\\x\\RPA 2026 - 13702784.doc", "13702784"),
    ],
)
def test_numero_rpa_do_arquivo(nome, esperado):
    assert numero_rpa_do_arquivo(nome) == esperado


@pytest.mark.parametrize("nome", ["RPA ELON.doc", "RPA 2026.doc", "RPA 1234567890.doc"])
def test_numero_rpa_ausente_ou_invalido(nome):
    with pytest.raises(ErroLeituraRpa):
        numero_rpa_do_arquivo(nome)
