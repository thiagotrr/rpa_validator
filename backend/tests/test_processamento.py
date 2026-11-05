import pytest

from app.extracao.extrator_texto import ErroExtracao
from app.extracao.processamento import processar_rpa
from tests.fixtures import textos_rpa as t

ARQ = "RPA - FULANO - 13915419.doc"


class Extrator:
    def __init__(self, texto=None, erro=None):
        self.texto, self.erro, self.chamadas = texto, erro, 0

    def __call__(self, conteudo, nome):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.texto


def test_auto_usa_texto_nativo_quando_completo():
    nativo, ocr = Extrator(t.A_IRRF_BRANCO), Extrator(t.A_IRRF_BRANCO)
    r = processar_rpa(b"x", ARQ, "2026-10", "auto", nativo=nativo, ocr=ocr)
    assert r.metodo_extracao == "nativo"
    assert ocr.chamadas == 0


def test_auto_cai_para_ocr_quando_faltam_campos():
    nativo, ocr = Extrator(t.ILEGIVEL), Extrator(t.A_IRRF_BRANCO)
    r = processar_rpa(b"x", ARQ, "2026-10", "auto", nativo=nativo, ocr=ocr)
    assert r.metodo_extracao == "ocr"
    assert r.inss == 14652


def test_auto_mantem_nativo_se_ocr_nao_for_melhor():
    nativo, ocr = Extrator(t.SEM_EMISSAO.replace("Nova Lima - MG, 20 de outubro de 2026", "")), Extrator(t.ILEGIVEL)
    r = processar_rpa(b"x", ARQ, "2026-10", "auto", nativo=nativo, ocr=ocr)
    assert r.metodo_extracao == "nativo"
    assert r.campos_ausentes == ("data_emissao",)


def test_auto_usa_ocr_quando_conversao_nativa_falha():
    nativo, ocr = Extrator(erro=ErroExtracao("falhou")), Extrator(t.A_IRRF_BRANCO)
    assert processar_rpa(b"x", ARQ, "2026-10", "auto", nativo=nativo, ocr=ocr).metodo_extracao == "ocr"


def test_native_nunca_chama_ocr():
    nativo, ocr = Extrator(t.ILEGIVEL), Extrator(t.A_IRRF_BRANCO)
    r = processar_rpa(b"x", ARQ, "2026-10", "native", nativo=nativo, ocr=ocr)
    assert r.metodo_extracao == "nativo" and ocr.chamadas == 0


def test_ocr_forcado():
    nativo, ocr = Extrator(t.A_IRRF_BRANCO), Extrator(t.A_IRRF_BRANCO)
    assert processar_rpa(b"x", ARQ, "2026-10", "ocr", nativo=nativo, ocr=ocr).metodo_extracao == "ocr"
    assert nativo.chamadas == 0


def test_modo_invalido():
    with pytest.raises(ValueError):
        processar_rpa(b"x", ARQ, "2026-10", "magico")
