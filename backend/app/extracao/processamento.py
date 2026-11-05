"""Estratégia de extração: texto nativo do Word primeiro; Tesseract quando faltar campo (ou se forçado)."""

from collections.abc import Callable

from app.dominio import RpaExtraido
from app.extracao.extrator_texto import ErroExtracao, texto_nativo, texto_ocr
from app.extracao.leitor_rpa import interpretar_rpa

Extrator = Callable[[bytes, str], str]
MODOS = ("auto", "native", "ocr")


def processar_rpa(
    conteudo: bytes,
    nome_arquivo: str,
    competencia: str,
    modo: str = "auto",
    nativo: Extrator = texto_nativo,
    ocr: Extrator = texto_ocr,
) -> RpaExtraido:
    if modo not in MODOS:
        raise ValueError(f"modo de extração inválido: {modo}")
    if modo == "ocr":
        return interpretar_rpa(ocr(conteudo, nome_arquivo), arquivo=nome_arquivo, competencia=competencia, metodo="ocr")

    try:
        rpa = interpretar_rpa(
            nativo(conteudo, nome_arquivo), arquivo=nome_arquivo, competencia=competencia, metodo="nativo"
        )
    except ErroExtracao:
        if modo == "native":
            raise
        rpa = None

    if modo == "native" or (rpa is not None and not rpa.campos_ausentes):
        return rpa

    rpa_ocr = interpretar_rpa(ocr(conteudo, nome_arquivo), arquivo=nome_arquivo, competencia=competencia, metodo="ocr")
    if rpa is None or len(rpa_ocr.campos_ausentes) < len(rpa.campos_ausentes):
        return rpa_ocr
    return rpa
