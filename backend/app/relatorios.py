"""Relatório consolidado: dict (JSON da API, que alimenta a tela), Markdown e PDF, todos do mesmo Relatorio."""

from dataclasses import asdict
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.dinheiro import centavos_para_brl
from app.dominio import Relatorio

ROTULOS_CAMPO = {
    "registro": "Registro",
    "inss": "INSS",
    "irrf": "IRRF",
    "sest_senat": "SEST/SENAT",
    "data_emissao": "Data de emissão",
    "data_nascimento": "Data de nascimento",
}
ROTULOS_TIPO = {
    "VALOR_DIFERENTE": "Valor diferente",
    "DATA_DIFERENTE": "Data diferente",
    "DATA_FORA_COMPETENCIA": "Emissão fora da competência",
    "CAMPO_NAO_EXTRAIDO": "Campo não extraído",
    "RPA_SEM_REFERENCIA": "RPA sem linha na planilha",
    "REFERENCIA_SEM_RPA": "Linha da planilha sem RPA",
}
_MODELOS = Path(__file__).parent / "modelos"


def relatorio_para_dicionario(r: Relatorio) -> dict:
    d = asdict(r)
    for div in d["divergencias"]:
        div["tipo"] = div["tipo"].value
    return d


def _md(v: object) -> str:
    """Escapa o que quebraria uma tabela Markdown."""
    return "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")


def _env(autoescape: bool) -> Environment:
    # autoescape explícito: select_autoescape(["html"]) NÃO cobre "relatorio_pdf.html.j2" (extensão .j2).
    env = Environment(loader=FileSystemLoader(_MODELOS), autoescape=autoescape, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(
        brl=centavos_para_brl, md=_md, campo=lambda c: ROTULOS_CAMPO.get(c, c), tipo=lambda t: ROTULOS_TIPO.get(t, t)
    )
    return env


def gerar_markdown(r: Relatorio) -> str:
    return _env(False).get_template("relatorio.md.j2").render(r=relatorio_para_dicionario(r))


def _html_do_pdf(r: Relatorio) -> str:
    """HTML interno: só alimenta o PDF. Não é exportado nem exposto pela API."""
    return _env(True).get_template("relatorio_pdf.html.j2").render(r=relatorio_para_dicionario(r))


def gerar_pdf(r: Relatorio) -> bytes:
    from xhtml2pdf import pisa

    buf = BytesIO()
    resultado = pisa.CreatePDF(src=_html_do_pdf(r), dest=buf, encoding="utf-8")
    if resultado.err:
        raise RuntimeError("falha ao gerar PDF")
    return buf.getvalue()
