"""Textos de RPA com o MESMO layout dos documentos reais, mas com dados pessoais fictícios (LGPD).
Valores monetários e datas preservados para reproduzir os casos reais."""

CABECALHO = (
    "BAUMINAS LOG E TRANSPORTES S/A\t\tRODOVIA MG-030 – VILA NOVA SUICA \t\t"
    "CEP: 34.012-580– NOVA LIMA - MG\t\tC.N.P.J 14.429.795/0002-43    IE: 0018534720169\t\t\n\n"
    "Serviços de frete – C.C. 224451 – Operação Carga Seca\t\t\n"
)


def layout_a(
    emissao: str,
    bruto: str,
    inss: str,
    irrf: str,
    sest: str,
    liquido: str,
    nascimento: str = "05/04/1985",
    rodape: str = "20 de outubro de 2026",
) -> str:
    return (
        CABECALHO
        + f"DATA EMISSÃO: {emissao}\t\t\n"
        + "AUTONOMO: Fulano de Tal\t\tCPF: 000.000.000-00\t\tPIS: 0.000.000.000-0\t\t"
        + f"DATA NASCIMENTO: {nascimento}\t\t\n\n"
        + f"VALOR BRUTO:      {bruto}\t\tINSS:                        {inss}\t\t"
        + f"IRRF:                  {irrf}\t\tSEST/ SENAT:         {sest}\t\t"
        + f"VALOR LÍQUIDO:    {liquido}\t\tVENCIMENTO: Pagamento efetuado\t\t"
        + "VALOR POR EXTENSO: (omitido)\t\t\n\n\n"
        + f"Nova Lima - MG, {rodape}"
    )


# Layout A — IRRF em branco (RPA real 13915419)
A_IRRF_BRANCO = layout_a("20/10/2026", "6.659,92", "146,52", "", "33,30", "6.480,10")
# Layout A — "INSS: 53,86" colado ao rótulo, IRRF em branco (RPA real 14037118)
A_INSS_COLADO = (
    CABECALHO
    + "DATA EMISSÃO: 24/10/2026\t\t\n"
    + "AUTONOMO: Fulano de Tal\t\tCPF: 000.000.000-00\t\tDATA NASCIMENTO: 05/04/1985\t\t\n\n"
    + "VALOR BRUTO:      6.659,92\t\tINSS: 53,86                 \t\tIRRF:                  \t\t"
    + "SEST/ SENAT: 33,30 \t\tVALOR LÍQUIDO: 6.572,76\t\tVENCIMENTO: Pagamento efetuado\n"
)
# Layout A — "R$ 0,0" (RPA real 14037076)
A_ZERO_CURTO = layout_a(
    "24/10/2026",
    "R$ 5.843,20",
    "R$ 128,55",
    "R$ 0,0",
    "R$ 29,22",
    "R$ 5.685,43",
    nascimento="17/01/1958",
    rodape="24 de outubro de 2026",
)
# Layout B — rótulos em linhas próprias e "Emissão:" na linha do valor bruto (RPA real 14070887)
B_LINHAS = (
    "BAUMINAS LOG E TRANSPORTES S/A\n\nRODOVIA MG-030 – VILA NOVA SUICA \n"
    "Autônomo: FULANO DE TAL  \nCPF: 000.000.000-00\nPIS: 000.00000.00-0\n"
    "Data de Nascimento: 10/11/1985\n\t\n"
    "Serviços de frete – C.C. 224451 – Operação Carga Seca\n\n"
    "Valor bruto:      R$       3.446,93                  Emissão: 26/10/2026\n\n"
    "INSS                   R$         75,83\n"
    "IRRF                   R$         0,00     \n"
    "SEST/ SENAT    R$         17,23            Vencimento: Pagto efetuado\n\n"
    "Valor líquido:     R$    3.353,87\t\n\n"
    "Nova Lima - MG, 26 de outubro de 2026."
)
# Casos de divergência real
A_SEST_TRUNCADO = layout_a(
    "14/10/2026",
    "R$ 20.677,30",
    "R$ 454,90",
    "",
    "R$ 103,38",
    "R$ 20.119,02",
    nascimento="30/07/1990",
    rodape="14 de outubro de 2026",
)  # RPA 13809297
A_INSS_DIVERGENTE = layout_a(
    "27/10/2026",
    "R$ 5.833,24",
    "R$ 86,81",
    "",
    "R$ 29,17",
    "R$ 5.717,26",
    nascimento="17/01/1958",
    rodape="27 de outubro de 2026",
)  # RPA 14090502
# Sem "DATA EMISSÃO": a data sai do rodapé
SEM_EMISSAO = A_IRRF_BRANCO.replace("DATA EMISSÃO: 20/10/2026", "")
# Texto ruim (ex.: OCR falhou)
ILEGIVEL = "B4UM1NAS L0G ... ### texto sem rótulos reconhecíveis"
