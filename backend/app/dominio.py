"""Modelos de domínio. Dinheiro em centavos (int); datas como datetime.date."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

# Lista única dos campos de imposto comparados. Não é variável de ambiente: existe para que
# leitor do RPA, comparação, relatório e front-end usem exatamente o mesmo conjunto.
CAMPOS_IMPOSTO = ("inss", "irrf", "sest_senat")
CAMPOS_DATA = ("data_emissao", "data_nascimento")
CAMPO_REGISTRO = "registro"  # divergências de existência (RPA sem linha / linha sem RPA)
ORDEM_CAMPOS = (CAMPO_REGISTRO, *CAMPOS_IMPOSTO, *CAMPOS_DATA)


@dataclass(frozen=True)
class LinhaPlanilha:
    """Linha da planilha que tem número de recibo (RPA)."""

    competencia: str  # "AAAA-MM"
    codigo_empresa: str
    cnpj: str
    aba: str
    numero_linha: int
    numero_rpa: str
    matricula: str
    nome: str
    valor_bruto: int
    inss: int
    irrf: int
    sest_senat: int
    data_nascimento: date | None
    conteudo: dict[str, str] = field(default_factory=dict)  # todas as células da linha, como texto


@dataclass(frozen=True)
class LinhaSemRecibo:
    """Linha com conteúdo mas sem número de recibo (ex.: total). Persistida, não comparada."""

    numero_linha: int
    conteudo: dict[str, str]


@dataclass(frozen=True)
class AbaPlanilha:
    aba: str
    codigo_empresa: str
    cnpj: str
    competencia: str
    linhas: tuple[LinhaPlanilha, ...]
    linhas_sem_recibo: tuple[LinhaSemRecibo, ...] = ()


@dataclass(frozen=True)
class RpaExtraido:
    competencia: str
    numero_rpa: str
    arquivo: str
    metodo_extracao: str  # "nativo" | "ocr"
    data_emissao: date | None
    data_nascimento: date | None
    valor_bruto: int | None
    inss: int | None
    irrf: int | None
    sest_senat: int | None
    campos_ausentes: tuple[str, ...] = ()


class TipoDivergencia(StrEnum):
    VALOR_DIFERENTE = "VALOR_DIFERENTE"
    DATA_DIFERENTE = "DATA_DIFERENTE"
    DATA_FORA_COMPETENCIA = "DATA_FORA_COMPETENCIA"
    CAMPO_NAO_EXTRAIDO = "CAMPO_NAO_EXTRAIDO"
    RPA_SEM_REFERENCIA = "RPA_SEM_REFERENCIA"
    REFERENCIA_SEM_RPA = "REFERENCIA_SEM_RPA"


@dataclass(frozen=True)
class Divergencia:
    numero_rpa: str
    codigo_empresa: str | None
    nome: str | None  # sempre ofuscado: primeiro nome + iniciais dos sobrenomes
    campo: str
    tipo: TipoDivergencia
    valor_planilha: str | None
    valor_documento: str | None
    diferenca_centavos: int | None = None


@dataclass(frozen=True)
class Relatorio:
    competencia: str
    gerado_em: str  # ISO-8601 UTC
    tolerancia_centavos: int
    qtd_documentos: int
    valor_total_documentos: int  # centavos (soma do valor bruto dos RPAs)
    qtd_linhas_referencia: int
    qtd_divergencias: int
    divergencias_por_campo: dict[str, int]
    divergencias: tuple[Divergencia, ...]
