"""Lê a planilha de conferência: uma aba por empresa; cabeçalho localizado pelo rótulo da coluna do recibo."""

import re
import unicodedata
from datetime import date, datetime
from io import BytesIO

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from app.configuracao import Configuracao
from app.dinheiro import numero_para_centavos
from app.dominio import AbaPlanilha, LinhaPlanilha, LinhaSemRecibo

OBRIGATORIAS = ("numero_rpa", "nome", "valor_bruto", "sest_senat", "inss", "irrf")
CAMPOS_MONETARIOS = ("valor_bruto", "inss", "irrf", "sest_senat")
LINHAS_BUSCA_CABECALHO = 20


class ErroPlanilha(ValueError):
    pass


def _rotulo(v: object) -> str:
    s = unicodedata.normalize("NFKC", str(v or "")).upper()
    return re.sub(r"\s+", " ", s).strip()


def _texto(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _valor_como_texto(v: object) -> str:
    """Preserva o valor da célula sem passar por aritmética de float (repr é exato e reversível)."""
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v).strip()


def _competencia(v: object, aba: str) -> str:
    if isinstance(v, (datetime, date)):
        return f"{v.year:04d}-{v.month:02d}"
    raise ErroPlanilha(f"aba {aba!r}: competência (data) não encontrada na célula configurada")


def _data(v: object) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", str(v).strip())
    if not m:
        raise ValueError(f"data inválida: {v!r}")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def _localizar_cabecalho(ws: Worksheet, cfg: Configuracao) -> tuple[int, dict[str, int], dict[int, str]] | None:
    """-> (linha do cabeçalho, campo -> coluna, coluna -> rótulo original)"""
    ancora = _rotulo(cfg.sheet_colunas["numero_rpa"])
    procurados = {_rotulo(rotulo): campo for campo, rotulo in cfg.sheet_colunas.items()}
    for linha in ws.iter_rows(min_row=1, max_row=LINHAS_BUSCA_CABECALHO):
        rotulos = {_rotulo(c.value): c.column for c in linha if c.value is not None}
        if ancora not in rotulos:
            continue
        mapa = {procurados[r]: col for r, col in rotulos.items() if r in procurados}
        faltando = [c for c in OBRIGATORIAS if c not in mapa]
        if faltando:
            raise ErroPlanilha(f"aba {ws.title!r}: colunas obrigatórias ausentes: {', '.join(faltando)}")
        originais = {c.column: str(c.value).strip() for c in linha if c.value is not None}
        return linha[0].row, mapa, originais
    return None


def _centavos(valor: object, formula: object) -> int:
    """Vazio = 0 (D6). Exceção: célula com fórmula sem valor calculado — não dá para saber o valor."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if isinstance(formula, str) and formula.startswith("="):
            raise ValueError("fórmula sem valor calculado")
        return 0
    return numero_para_centavos(valor)


def _ler_aba(ws: Worksheet, ws_formulas: Worksheet, cfg: Configuracao) -> AbaPlanilha | None:
    cab = _localizar_cabecalho(ws, cfg)
    if cab is None:
        return None
    linha_cab, mapa, originais = cab
    competencia = _competencia(ws[cfg.sheet_competencia_cell].value, ws.title)
    codigo = _texto(ws[cfg.sheet_codigo_empresa_cell].value)
    if not codigo:
        raise ErroPlanilha(f"aba {ws.title!r}: código da empresa vazio em {cfg.sheet_codigo_empresa_cell}")
    cnpj = re.sub(r"\s+", "", _texto(ws[cfg.sheet_cnpj_cell].value))

    linhas: list[LinhaPlanilha] = []
    sem_recibo: list[LinhaSemRecibo] = []
    for r in range(linha_cab + 1, ws.max_row + 1):
        conteudo = {
            originais[col]: _valor_como_texto(v)
            for col in originais
            if (v := ws.cell(row=r, column=col).value) is not None and str(v).strip() != ""
        }
        if not conteudo:
            continue
        val = {campo: ws.cell(row=r, column=col).value for campo, col in mapa.items()}
        numero = _texto(val["numero_rpa"])
        if not numero:  # ex.: linha de total — guardada, não comparada
            sem_recibo.append(LinhaSemRecibo(numero_linha=r, conteudo=conteudo))
            continue
        try:
            monet = {c: _centavos(val[c], ws_formulas.cell(row=r, column=mapa[c]).value) for c in CAMPOS_MONETARIOS}
            linhas.append(
                LinhaPlanilha(
                    competencia=competencia,
                    codigo_empresa=codigo,
                    cnpj=cnpj,
                    aba=ws.title,
                    numero_linha=r,
                    numero_rpa=numero,
                    matricula=_texto(val.get("matricula")),
                    nome=_texto(val["nome"]),
                    data_nascimento=_data(val.get("data_nascimento")),
                    conteudo=conteudo,
                    **monet,
                )
            )
        except ValueError as e:
            raise ErroPlanilha(
                f"aba {ws.title!r}, linha {r} (RPA {numero}): {e}. Se a célula tem fórmula, "
                "abra e salve o arquivo no Excel para gravar os valores calculados."
            ) from e
    return AbaPlanilha(
        aba=ws.title,
        codigo_empresa=codigo,
        cnpj=cnpj,
        competencia=competencia,
        linhas=tuple(linhas),
        linhas_sem_recibo=tuple(sem_recibo),
    )


def ler_planilha(conteudo: bytes, cfg: Configuracao) -> list[AbaPlanilha]:
    try:
        wb = openpyxl.load_workbook(BytesIO(conteudo), data_only=True)
        wb_formulas = openpyxl.load_workbook(BytesIO(conteudo), data_only=False)
    except Exception as e:  # arquivo corrompido / não é xlsx
        raise ErroPlanilha(f"arquivo não é uma planilha .xlsx válida: {e}") from e

    abas = [a for ws in wb.worksheets if (a := _ler_aba(ws, wb_formulas[ws.title], cfg)) is not None]
    if not abas:
        raise ErroPlanilha(f"nenhuma aba com cabeçalho {cfg.sheet_colunas['numero_rpa']!r} encontrada")
    if len({a.competencia for a in abas}) > 1:
        raise ErroPlanilha("abas com competências diferentes no mesmo arquivo")
    codigos = [a.codigo_empresa for a in abas]
    if len(codigos) != len(set(codigos)):
        raise ErroPlanilha("código de empresa repetido em mais de uma aba")
    numeros = [ln.numero_rpa for a in abas for ln in a.linhas]
    duplicados = sorted({n for n in numeros if numeros.count(n) > 1})
    if duplicados:
        raise ErroPlanilha(f"número de RPA repetido na planilha: {', '.join(duplicados)}")
    return abas
