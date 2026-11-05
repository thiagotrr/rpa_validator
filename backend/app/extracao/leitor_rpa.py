"""Extrai campos de impostos e datas do TEXTO de um RPA (nativo ou OCR). Determinístico, sem IA."""

import re
import unicodedata
from datetime import date

from app.dinheiro import brl_para_centavos
from app.dominio import RpaExtraido

_NUM = r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})+,\d{1,2}|\d+,\d{1,2})?"
_ROTULOS_VALOR = {
    "valor_bruto": r"VALOR\s+BRUTO\s*:?",
    "inss": r"(?<![A-Z])INSS\s*:?",
    "irrf": r"(?<![A-Z])IRRF\s*:?",
    "sest_senat": r"SEST\s*/\s*SENAT\s*:?",
}
# Rótulo presente sem número = não houve retenção (ex.: "IRRF:" em branco) -> 0.
_VAZIO_SIGNIFICA_ZERO = {"inss", "irrf", "sest_senat"}

_EMISSAO = re.compile(r"EMISSAO\s*:?\s*(\d{2})/(\d{2})/(\d{4})")
_NASCIMENTO = re.compile(r"NASCIMENTO\s*:?\s*(\d{2})/(\d{2})/(\d{4})")
_MESES = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}
_RODAPE = re.compile(r"(\d{1,2})\s+DE\s+(" + "|".join(_MESES) + r")\s+DE\s+(\d{4})")
_NUMERO_RPA = re.compile(r"(?<!\d)(\d{7,9})(?!\d)")


class ErroLeituraRpa(ValueError):
    pass


def normalizar(texto: str) -> str:
    """Maiúsculas e sem acentos: 'Emissão' -> 'EMISSAO', 'LÍQUIDO' -> 'LIQUIDO'."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


def numero_rpa_do_arquivo(nome_arquivo: str) -> str:
    """O número do RPA só existe no nome do arquivo: 'RPA - ELON MEIRA - 14101817.doc' -> '14101817'."""
    base = re.split(r"[\\/]", nome_arquivo)[-1]
    base = re.sub(r"\.(docx?|DOCX?)$", "", base)
    encontrados = _NUMERO_RPA.findall(base)
    if not encontrados:
        raise ErroLeituraRpa(f"número do RPA não encontrado no nome do arquivo: {nome_arquivo!r}")
    return encontrados[-1]


def _data(regex: re.Pattern, texto: str) -> date | None:
    m = regex.search(texto)
    if not m:
        return None
    dia, mes, ano = (int(g) for g in m.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _data_rodape(texto: str) -> date | None:
    m = _RODAPE.search(texto)
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def interpretar_rpa(texto: str, *, arquivo: str, competencia: str, metodo: str) -> RpaExtraido:
    n = normalizar(texto)
    valores: dict[str, int | None] = {}
    ausentes: list[str] = []
    for campo, rotulo in _ROTULOS_VALOR.items():
        # [ \t]* não atravessa quebra de linha: um rótulo vazio nunca "rouba" o número do campo seguinte.
        m = re.search(rotulo + r"[ \t]*" + _NUM, n)
        if m is None:
            valores[campo] = None
            ausentes.append(campo)
        elif m.group(1) is None:
            if campo in _VAZIO_SIGNIFICA_ZERO:
                valores[campo] = 0
            else:
                valores[campo] = None
                ausentes.append(campo)
        else:
            valores[campo] = brl_para_centavos(m.group(1))

    emissao = _data(_EMISSAO, n) or _data_rodape(n)
    if emissao is None:
        ausentes.append("data_emissao")
    nascimento = _data(_NASCIMENTO, n)
    if nascimento is None:
        ausentes.append("data_nascimento")

    return RpaExtraido(
        competencia=competencia,
        numero_rpa=numero_rpa_do_arquivo(arquivo),
        arquivo=arquivo,
        metodo_extracao=metodo,
        data_emissao=emissao,
        data_nascimento=nascimento,
        valor_bruto=valores["valor_bruto"],
        inss=valores["inss"],
        irrf=valores["irrf"],
        sest_senat=valores["sest_senat"],
        campos_ausentes=tuple(ausentes),
    )
