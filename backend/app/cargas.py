"""Regras das duas cargas, separadas das rotas para serem testadas sem HTTP.

- Planilha: o arquivo SUBSTITUI a competência inteira (todas as empresas); aba com erro é recusada sozinha.
- RPAs: carga COMPLEMENTAR. Quem já está na collection não é reprocessado (a menos que se peça para substituir)
  e o quantitativo é conferido com a planilha ANTES do envio, sem bloquear.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from app.configuracao import Configuracao
from app.dominio import AbaPlanilha
from app.extracao.leitor_rpa import ErroLeituraRpa, numero_rpa_do_arquivo
from app.leitor_planilha import ler_planilha
from app.repositorio import Repositorio

Prevalece = Literal["arquivo", "tela"]
Decisao = Literal["processar", "repetido_no_envio", "ja_carregado"]


class CompetenciaDivergente(Exception):
    """A competência escolhida na tela não é a da planilha (célula A2). Nada foi gravado."""

    def __init__(self, competencia_arquivo: str, competencia_informada: str):
        super().__init__(
            f"a planilha é de {competencia_arquivo}, mas a competência informada é {competencia_informada}"
        )
        self.competencia_arquivo = competencia_arquivo
        self.competencia_informada = competencia_informada


@dataclass(frozen=True)
class ResultadoCargaPlanilha:
    competencia: str
    competencia_arquivo: str
    abas: list[dict]
    erros_abas: list[dict]
    qtd_linhas_substituidas: int  # linhas da competência que existiam antes e foram trocadas


@dataclass(frozen=True)
class VerificacaoEnvio:
    competencia: str
    planilha_carregada: bool
    qtd_linhas_planilha: int
    qtd_arquivos: int  # nomes recebidos
    qtd_sem_numero: int  # nome sem número de RPA (vai falhar na carga)
    qtd_repetidos_no_envio: int  # mesmo número em mais de um arquivo do envio
    qtd_ja_carregados: int  # RPAs da competência que já estão na collection, antes deste envio
    qtd_ja_existentes_no_envio: int  # números deste envio que já estão na collection
    qtd_novos: int
    qtd_total_apos_envio: int  # já carregados + novos
    diferenca: int  # total após o envio - linhas da planilha (negativo = faltam RPAs)
    confere: bool


def reatribuir_competencia(aba: AbaPlanilha, competencia: str) -> AbaPlanilha:
    if aba.competencia == competencia:
        return aba
    linhas = tuple(replace(ln, competencia=competencia) for ln in aba.linhas)
    return replace(aba, competencia=competencia, linhas=linhas)


def resumo_aba(aba: AbaPlanilha) -> dict:
    return {
        "aba": aba.aba,
        "codigo_empresa": aba.codigo_empresa,
        "cnpj": aba.cnpj,
        "competencia": aba.competencia,
        "qtd_linhas": len(aba.linhas),
        "qtd_linhas_sem_recibo": len(aba.linhas_sem_recibo),
    }


def carregar_planilha(
    conteudo: bytes,
    *,
    cfg: Configuracao,
    repo: Repositorio,
    competencia_informada: str,
    prevalece: Prevalece | None,
    arquivo: str,
    usuario: str,
    agora: datetime,
) -> ResultadoCargaPlanilha:
    """Levanta ErroPlanilha (arquivo inválido) ou CompetenciaDivergente (sem `prevalece`); nos dois casos
    nada é gravado nem apagado."""
    lida = ler_planilha(conteudo, cfg)
    competencia_arquivo = lida.abas[0].competencia
    if competencia_arquivo != competencia_informada and prevalece is None:
        raise CompetenciaDivergente(competencia_arquivo, competencia_informada)
    competencia = competencia_informada if prevalece == "tela" else competencia_arquivo
    abas = [reatribuir_competencia(a, competencia) for a in lida.abas]
    substituidas = len(repo.listar_planilha(competencia))
    repo.substituir_planilha(competencia, abas, arquivo=arquivo, usuario=usuario, agora=agora)
    return ResultadoCargaPlanilha(
        competencia=competencia,
        competencia_arquivo=competencia_arquivo,
        abas=[resumo_aba(a) for a in abas],
        erros_abas=[{"aba": e.aba, "mensagem": e.mensagem} for e in lida.erros],
        qtd_linhas_substituidas=substituidas,
    )


def situacao_planilha(repo: Repositorio, competencia: str) -> dict:
    linhas = repo.listar_planilha(competencia)
    return {
        "competencia": competencia,
        "carregada": bool(linhas),
        "qtd_linhas": len(linhas),
        "empresas": sorted({ln.codigo_empresa for ln in linhas}),
    }


def verificar_envio_rpas(repo: Repositorio, competencia: str, nomes: list[str]) -> VerificacaoEnvio:
    """Só olha os NOMES dos arquivos (o número do RPA vem do nome). Informa; quem decide é o usuário."""
    linhas = len(repo.listar_planilha(competencia))
    ja_carregados = repo.numeros_rpas(competencia)
    numeros: list[str] = []
    sem_numero = 0
    for nome in nomes:
        try:
            numeros.append(numero_rpa_do_arquivo(nome))
        except ErroLeituraRpa:
            sem_numero += 1
    distintos = set(numeros)
    total = len(ja_carregados | distintos)
    return VerificacaoEnvio(
        competencia=competencia,
        planilha_carregada=linhas > 0,
        qtd_linhas_planilha=linhas,
        qtd_arquivos=len(nomes),
        qtd_sem_numero=sem_numero,
        qtd_repetidos_no_envio=len(numeros) - len(distintos),
        qtd_ja_carregados=len(ja_carregados),
        qtd_ja_existentes_no_envio=len(distintos & ja_carregados),
        qtd_novos=len(distintos - ja_carregados),
        qtd_total_apos_envio=total,
        diferenca=total - linhas,
        confere=linhas > 0 and total == linhas,
    )


def decidir_arquivo(numero_rpa: str, *, vistos: set[str], ja_carregados: set[str], substituir: bool) -> Decisao:
    """O que fazer com um arquivo do envio, antes de gastar LibreOffice nele. Atualiza `vistos`."""
    if numero_rpa in vistos:
        return "repetido_no_envio"
    vistos.add(numero_rpa)
    if numero_rpa in ja_carregados and not substituir:
        return "ja_carregado"
    return "processar"
