"""Rotas das duas cargas (planilha e RPAs). A autenticação entra por `usuario_atual` (definida em criar_aplicacao)."""

import logging
import re
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app import cargas
from app.configuracao import Configuracao
from app.dominio import RpaExtraido
from app.extracao.extrator_texto import ErroExtracao
from app.extracao.leitor_rpa import ErroLeituraRpa, numero_rpa_do_arquivo
from app.leitor_planilha import ErroPlanilha
from app.repositorio import Repositorio

log = logging.getLogger("rpa")
_COMPETENCIA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
Processador = Callable[[bytes, str, str, str], RpaExtraido]


class DadosVerificacao(BaseModel):
    competencia: str
    arquivos: list[str]  # só os nomes: o número do RPA está no nome e nada pesado trafega


def validar_competencia(c: str) -> str:
    if not _COMPETENCIA.match(c):
        raise HTTPException(422, "competência deve estar no formato AAAA-MM")
    return c


def ler_upload(arquivo: UploadFile, cfg: Configuracao, extensoes: tuple[str, ...]) -> bytes:
    nome = arquivo.filename or ""
    if not nome.lower().endswith(extensoes):
        raise HTTPException(415, f"{nome or 'arquivo'}: extensão não aceita (esperado {', '.join(extensoes)})")
    limite = cfg.max_upload_mb * 1024 * 1024
    conteudo = arquivo.file.read(limite + 1)
    if len(conteudo) > limite:
        raise HTTPException(413, f"{nome}: maior que {cfg.max_upload_mb} MB")
    return conteudo


def _agora() -> datetime:
    return datetime.now(UTC)


def registrar_rotas_carga(
    app: FastAPI,
    *,
    cfg: Configuracao,
    repositorio: Repositorio,
    processador: Processador,
    usuario_atual: Callable[..., str],
    mascarar_email: Callable[[str], str],
    agora: Callable[[], datetime] = _agora,
) -> None:
    Usuario = Annotated[str, Depends(usuario_atual)]

    @app.post("/api/planilhas")
    def carregar_planilha(
        usuario: Usuario,
        arquivo: Annotated[UploadFile, File()],
        competencia: Annotated[str, Form()],
        prevalece: Annotated[Literal["arquivo", "tela"] | None, Form()] = None,
    ):
        validar_competencia(competencia)
        conteudo = ler_upload(arquivo, cfg, (".xlsx",))
        try:
            r = cargas.carregar_planilha(
                conteudo,
                cfg=cfg,
                repo=repositorio,
                competencia_informada=competencia,
                prevalece=prevalece,
                arquivo=arquivo.filename or "",
                usuario=usuario,
                agora=agora(),
            )
        except ErroPlanilha as e:
            # a mensagem pode ecoar valor de célula (dinheiro inválido): vai na resposta 422, não no log
            log.warning("planilha_rejeitada", extra={"arquivo": arquivo.filename})
            raise HTTPException(422, str(e)) from e
        except cargas.CompetenciaDivergente as e:
            raise HTTPException(
                409,
                {
                    "codigo": "competencia_divergente",
                    "mensagem": str(e),
                    "competencia_arquivo": e.competencia_arquivo,
                    "competencia_informada": e.competencia_informada,
                },
            ) from e
        log.info(
            "planilha_carregada",
            extra={
                "arquivo": arquivo.filename,
                "usuario": mascarar_email(usuario),
                "competencia": r.competencia,
                "qtd_abas": len(r.abas),
                "abas_com_erro": len(r.erros_abas),
                "linhas_substituidas": r.qtd_linhas_substituidas,
            },
        )
        return asdict(r)

    @app.get("/api/planilhas/{competencia}")
    def consultar_planilha(competencia: str, usuario: Usuario):
        return cargas.situacao_planilha(repositorio, validar_competencia(competencia))

    @app.post("/api/rpas/verificacao")
    def verificar_rpas(dados: DadosVerificacao, usuario: Usuario):
        validar_competencia(dados.competencia)
        return asdict(cargas.verificar_envio_rpas(repositorio, dados.competencia, dados.arquivos))

    @app.post("/api/rpas")
    def carregar_rpas(
        usuario: Usuario,
        competencia: Annotated[str, Form()],
        arquivos: Annotated[list[UploadFile], File()],
        substituir: Annotated[bool, Form()] = False,
    ):
        validar_competencia(competencia)
        if len(arquivos) > cfg.max_arquivos_por_lote:
            raise HTTPException(413, f"máximo de {cfg.max_arquivos_por_lote} arquivos por envio")
        if not cargas.situacao_planilha(repositorio, competencia)["carregada"]:
            raise HTTPException(
                409,
                {
                    "codigo": "sem_planilha",
                    "mensagem": f"nenhuma planilha carregada para {competencia}; carregue a planilha antes dos RPAs",
                },
            )
        ja_carregados, vistos, momento = repositorio.numeros_rpas(competencia), set(), agora()
        resultados = []
        for arq in arquivos:
            nome = arq.filename or ""
            try:
                numero = numero_rpa_do_arquivo(nome)
                decisao = cargas.decidir_arquivo(
                    numero, vistos=vistos, ja_carregados=ja_carregados, substituir=substituir
                )
                if decisao == "repetido_no_envio":
                    raise ErroLeituraRpa(f"RPA {numero} repetido neste envio")
                if decisao == "ja_carregado":
                    resultados.append({"arquivo": nome, "status": "ja_carregado", "numero_rpa": numero})
                    continue
                conteudo = ler_upload(arq, cfg, (".doc", ".docx"))
                rpa = processador(conteudo, nome, competencia, cfg.extraction_mode)
                del conteudo  # o binário não é guardado em lugar nenhum
                try:
                    repositorio.salvar_rpa(rpa, usuario=usuario, agora=momento)
                except Exception as e:  # noqa: BLE001 - qualquer falha do repositório: segue o lote
                    log.error("rpa_falha_ao_gravar", extra={"tipo_erro": type(e).__name__})
                    resultados.append({"arquivo": nome, "status": "erro", "erro": "falha ao gravar"})
                    continue
                resultados.append(
                    {
                        "arquivo": nome,
                        "status": "ok",
                        "numero_rpa": rpa.numero_rpa,
                        "metodo": rpa.metodo_extracao,
                        "campos_ausentes": list(rpa.campos_ausentes),
                    }
                )
            except HTTPException as e:
                resultados.append({"arquivo": nome, "status": "erro", "erro": e.detail})
            except (ErroLeituraRpa, ErroExtracao, ValueError) as e:
                resultados.append({"arquivo": nome, "status": "erro", "erro": str(e)})
        por_status = {s: sum(r["status"] == s for r in resultados) for s in ("ok", "erro", "ja_carregado")}
        log.info(
            "rpas_carregados",
            extra={
                "competencia": competencia,
                "ok": por_status["ok"],
                "erros": por_status["erro"],
                "ja_carregados": por_status["ja_carregado"],
                "substituir": substituir,
                "usuario": mascarar_email(usuario),  # nome de arquivo de RPA tem nome de pessoa: não vai ao log
            },
        )
        return {
            "competencia": competencia,
            "ok": por_status["ok"],
            "erros": por_status["erro"],
            "ja_carregados": por_status["ja_carregado"],
            "resultados": resultados,
        }
