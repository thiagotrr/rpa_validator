"""Comparação determinística planilha (referência) x RPAs (documentos), via DataFrames pandas."""

from collections import Counter
from dataclasses import asdict, fields
from datetime import UTC, date, datetime

import pandas as pd

from app.dinheiro import centavos_para_brl
from app.dominio import (
    CAMPO_REGISTRO,
    CAMPOS_IMPOSTO,
    ORDEM_CAMPOS,
    Divergencia,
    LinhaPlanilha,
    Relatorio,
    RpaExtraido,
    TipoDivergencia,
)
from app.privacidade import ofuscar_nome

COLUNAS_REF = [f.name for f in fields(LinhaPlanilha) if f.name != "conteudo"]
COLUNAS_RPA = [f.name for f in fields(RpaExtraido)]


def planilha_para_df(linhas: list[LinhaPlanilha]) -> pd.DataFrame:
    return pd.DataFrame([{c: getattr(ln, c) for c in COLUNAS_REF} for ln in linhas], columns=COLUNAS_REF, dtype=object)


def rpas_para_df(rpas: list[RpaExtraido]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in rpas], columns=COLUNAS_RPA, dtype=object)


def _v(x):
    """NaN/None do pandas -> None."""
    if x is None:
        return None
    try:
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return x


def _fmt_data(d: date | None) -> str | None:
    return d.strftime("%d/%m/%Y") if d else None


def comparar(
    df_ref: pd.DataFrame,
    df_rpa: pd.DataFrame,
    competencia: str,
    tolerancia_centavos: int,
    agora: datetime | None = None,
) -> Relatorio:
    """Impostos: vazio já chega como 0 dos dois lados (D6); diferença absoluta <= tolerância é ignorada (D5)."""
    ano, mes = (int(p) for p in competencia.split("-"))
    juncao = df_ref.merge(df_rpa, on="numero_rpa", how="outer", suffixes=("_ref", "_doc"), indicator=True)
    divs: list[Divergencia] = []

    for row in juncao.to_dict("records"):
        numero = str(row["numero_rpa"])
        empresa, nome = _v(row.get("codigo_empresa")), ofuscar_nome(_v(row.get("nome")))

        def add(campo, tipo, planilha=None, documento=None, diferenca=None, _n=numero, _e=empresa, _nm=nome):
            divs.append(Divergencia(_n, _e, _nm, campo, tipo, planilha, documento, diferenca))

        if row["_merge"] == "left_only":
            add(CAMPO_REGISTRO, TipoDivergencia.REFERENCIA_SEM_RPA, planilha="linha na planilha")
            continue
        if row["_merge"] == "right_only":
            add(CAMPO_REGISTRO, TipoDivergencia.RPA_SEM_REFERENCIA, documento=str(row["arquivo"]))
            continue

        for campo in CAMPOS_IMPOSTO:
            ref, doc = _v(row[f"{campo}_ref"]), _v(row[f"{campo}_doc"])
            if doc is None:
                add(campo, TipoDivergencia.CAMPO_NAO_EXTRAIDO, centavos_para_brl(int(ref)), None)
            elif abs(int(ref) - int(doc)) > tolerancia_centavos:
                add(
                    campo,
                    TipoDivergencia.VALOR_DIFERENTE,
                    centavos_para_brl(int(ref)),
                    centavos_para_brl(int(doc)),
                    int(doc) - int(ref),
                )

        emissao = _v(row["data_emissao"])
        if emissao is None:
            add("data_emissao", TipoDivergencia.CAMPO_NAO_EXTRAIDO, competencia, None)
        elif (emissao.year, emissao.month) != (ano, mes):
            add("data_emissao", TipoDivergencia.DATA_FORA_COMPETENCIA, competencia, _fmt_data(emissao))

        nasc_ref, nasc_doc = _v(row["data_nascimento_ref"]), _v(row["data_nascimento_doc"])
        if nasc_ref is not None:  # a planilha real ainda não traz a data; só compara quando houver
            if nasc_doc is None:
                add("data_nascimento", TipoDivergencia.CAMPO_NAO_EXTRAIDO, _fmt_data(nasc_ref), None)
            elif nasc_doc != nasc_ref:
                add("data_nascimento", TipoDivergencia.DATA_DIFERENTE, _fmt_data(nasc_ref), _fmt_data(nasc_doc))

    divs.sort(key=lambda d: (d.numero_rpa, ORDEM_CAMPOS.index(d.campo)))
    por_campo = Counter(d.campo for d in divs)
    brutos = [int(v) for v in df_rpa["valor_bruto"] if _v(v) is not None]
    return Relatorio(
        competencia=competencia,
        gerado_em=(agora or datetime.now(UTC)).isoformat(timespec="seconds"),
        tolerancia_centavos=tolerancia_centavos,
        qtd_documentos=len(df_rpa),
        valor_total_documentos=sum(brutos),
        qtd_linhas_referencia=len(df_ref),
        qtd_divergencias=len(divs),
        divergencias_por_campo={c: por_campo[c] for c in ORDEM_CAMPOS if por_campo[c]},
        divergencias=tuple(divs),
    )
