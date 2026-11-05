"""Gera planilhas sintéticas no layout da 'Nova Lima.xlsx' (sem dados pessoais).
Identificação provisória: código da empresa em E1, CNPJ em E2, competência em A2."""

from datetime import datetime
from io import BytesIO

import openpyxl

CABECALHO = [
    "Matr.",
    "Nome",
    None,
    "QUEM ENVIOU",
    "DATA NASC.",
    "C.P.F.",
    "P.I.S.",
    "Nº RECIBO",
    "VERBA 234",
    "BASE CÁLCULO INSS",
    "SEST/SENAT",
    "INSS EMPREGADO",
    "IR EMPREGADO",
    "INSS EMPRESA",
    "LÍQUIDO",
]


def linha(matr, nome, recibo, bruto, sest, inss, ir, nasc=None):
    """Valores com as casas decimais "cruas" que as fórmulas da planilha real produzem."""
    return [
        matr,
        nome,
        None,
        None,
        nasc,
        None,
        None,
        recibo,
        bruto,
        bruto * 0.2,
        sest,
        inss,
        ir,
        bruto * 0.02,
        bruto - sest - (inss or 0) - (ir or 0),
    ]


LINHAS_PADRAO = [
    linha(20024, "FULANO ALFA DA SILVA", "13915419", 6659.92, 33.2996, 146.51824, 0),
    linha(20024, "FULANO ALFA DA SILVA", "14037118", 6659.92, 33.2996, 53.86, 0),
    linha(20280, "FULANO BETA", "14070887", 3446.93, 17.23465, 75.83246, 0),
    linha(20289, "FULANO GAMA DE SOUZA", "13809297", 20677.3, 103.3865, 454.9006, 0),  # SEST 103,39 x doc 103,38
    linha(20279, "FULANO DELTA DE MELO", "14090502", 5833.24, 29.1662, 86.83, 0),  # INSS 86,83 x doc 86,81
    linha(20279, "FULANO DELTA DE MELO", "14037076", 5843.2, 29.216, 128.5504, None),  # IR vazio = 0
]


def gerar_xlsx(
    abas: dict[str, tuple[str, list[list]]] | None = None,
    competencia: datetime = datetime(2026, 10, 1),
    com_total: bool = True,
) -> bytes:
    """abas = {nome_aba: (codigo_empresa, linhas)}"""
    abas = abas or {"Planilha1": ("671", LINHAS_PADRAO)}
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nome, (codigo, linhas) in abas.items():
        ws = wb.create_sheet(nome)
        ws["A1"] = "LOG Nova Lima Autônomos (Frete)"
        ws["E1"] = int(codigo) if codigo.isdigit() else codigo
        ws["A2"] = competencia
        ws["E2"] = "14.429.795/0015 - 68"
        for i, rubrica in enumerate([234, 879, 779, 401, 405, 778, 799]):
            ws.cell(row=4, column=9 + i, value=rubrica)
        ws.append(CABECALHO)
        for li in linhas:
            ws.append(li)
        if com_total:
            ws.append([None] * 8 + [sum(li[8] for li in linhas)])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gerar_xlsx_com_formula_sem_cache() -> bytes:
    """Arquivo gerado por sistema e nunca aberto no Excel: a fórmula existe, o valor calculado não."""
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx(com_total=False)))
    wb["Planilha1"]["L6"] = "=J6*11%"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
