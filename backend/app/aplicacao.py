"""API FastAPI + front-end estático. Executar: uvicorn app.aplicacao:criar_aplicacao --factory"""

import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import autenticacao as acesso
from app.comparacao import comparar, planilha_para_df, rpas_para_df
from app.configuracao import Configuracao, obter_configuracao
from app.extracao.processamento import processar_rpa
from app.registro_logs import configurar_logs
from app.relatorios import gerar_markdown, gerar_pdf, relatorio_para_dicionario
from app.repositorio import Repositorio, criar_repositorio
from app.rotas_carga import Processador, registrar_rotas_carga, validar_competencia

log = logging.getLogger("rpa")
_MB = 1024 * 1024
_VARIAVEIS_EMULADOR = ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST")


class DadosEntrada(BaseModel):
    email: str
    senha: str


class DadosRenovacao(BaseModel):
    refresh_token: str


def _agora() -> datetime:
    return datetime.now(UTC)


def _sessao_para_resposta(s: acesso.SessaoAcesso) -> dict:
    return {
        "id_token": s.id_token,
        "refresh_token": s.refresh_token,
        "token_type": "bearer",
        "expira_em": s.expira_em.isoformat(),
    }


def _recusar_emulador_fora_de_demo(cfg: Configuracao) -> None:
    """Com emulador o Admin SDK aceita tokens sem assinatura: isso nunca pode valer num projeto real."""
    definidas = [v for v in _VARIAVEIS_EMULADOR if os.environ.get(v)]
    if definidas and not (cfg.gcp_project or "").startswith("demo-"):
        raise ValueError(
            f"variável de emulador definida ({', '.join(definidas)}) com GCP_PROJECT que não começa com 'demo-': "
            "recusando subir (tokens sem assinatura seriam aceitos)"
        )


def criar_aplicacao(
    cfg: Configuracao | None = None,
    repo: Repositorio | None = None,
    provedor: acesso.ProvedorIdentidade | None = None,
    processador: Processador = processar_rpa,
) -> FastAPI:
    cfg = cfg or obter_configuracao()
    configurar_logs()
    _recusar_emulador_fora_de_demo(cfg)
    if provedor is None:
        from app.provedor_firebase import ProvedorFirebase

        provedor = ProvedorFirebase(cfg.firebase_web_api_key, cfg.gcp_project)  # recusa subir sem a chave
    repositorio = repo or criar_repositorio(cfg.repository_backend, cfg.gcp_project, cfg.firestore_database)

    app = FastAPI(title="Validador de RPAs", docs_url="/api/docs", openapi_url="/api/openapi.json")
    portador = HTTPBearer(auto_error=False)
    # Limite do corpo inteiro do envio (o limite por arquivo só vale depois que o corpo já foi recebido).
    limites_de_corpo = {
        "/api/planilhas": (cfg.max_upload_mb + 1) * _MB,
        "/api/rpas": (cfg.max_upload_mb * cfg.max_arquivos_por_lote + 1) * _MB,
    }

    @app.middleware("http")
    async def registrar_requisicao(request: Request, call_next):
        inicio, rid = time.perf_counter(), request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        limite = limites_de_corpo.get(request.url.path) if request.method == "POST" else None
        tamanho = request.headers.get("content-length", "")
        if limite and tamanho.isdigit() and int(tamanho) > limite:
            resposta = JSONResponse({"detail": f"envio maior que o limite de {limite // _MB} MB"}, status_code=413)
        else:
            resposta = await call_next(request)
        if request.url.path.startswith("/api"):
            log.info(
                "requisicao",
                extra={
                    "request_id": rid,
                    "metodo": request.method,
                    "rota": request.url.path,
                    "status": resposta.status_code,
                    "duracao_ms": round((time.perf_counter() - inicio) * 1000),
                },
            )
        resposta.headers["x-request-id"] = rid
        return resposta

    def usuario_atual(cred: Annotated[HTTPAuthorizationCredentials | None, Depends(portador)]) -> str:
        if cred is None:
            raise HTTPException(401, "token ausente", headers={"WWW-Authenticate": "Bearer"})
        try:
            return acesso.validar_token(cred.credentials, cfg, provedor)
        except acesso.TokenInvalido:
            raise HTTPException(401, "token inválido ou expirado", headers={"WWW-Authenticate": "Bearer"}) from None
        except acesso.ErroProvedorIdentidade:
            raise HTTPException(503, "serviço de autenticação indisponível") from None

    Usuario = Annotated[str, Depends(usuario_atual)]

    @app.get("/healthz")
    def saude():
        return {"status": "ok"}

    @app.post("/api/acesso/entrar")
    def entrar(dados: DadosEntrada):
        agora, email = _agora(), acesso.mascarar_email(dados.email)
        try:
            sessao = acesso.autenticar(dados.email, dados.senha, cfg, repositorio, provedor, agora)
        except acesso.LoginBloqueado as e:
            log.warning("acesso_bloqueado", extra={"email": email})
            segundos = max(1, int((e.ate - agora).total_seconds()))
            return JSONResponse(
                {"detail": "muitas tentativas; tente novamente mais tarde", "bloqueado_ate": e.ate.isoformat()},
                status_code=429,
                headers={"Retry-After": str(segundos)},
            )
        except acesso.CredenciaisInvalidas:
            log.warning("acesso_negado", extra={"email": email})
            raise HTTPException(401, "e-mail ou senha inválidos") from None
        except acesso.ErroProvedorIdentidade as e:
            log.error("acesso_provedor_indisponivel", extra={"erro": str(e)})
            raise HTTPException(503, "serviço de autenticação indisponível") from None
        log.info("acesso_ok", extra={"email": email})
        return _sessao_para_resposta(sessao)

    @app.post("/api/acesso/renovar")
    def renovar_sessao(dados: DadosRenovacao):
        try:
            return _sessao_para_resposta(acesso.renovar(dados.refresh_token, cfg, provedor, _agora()))
        except acesso.TokenInvalido:
            raise HTTPException(401, "sessão expirada; entre novamente") from None
        except acesso.ErroProvedorIdentidade:
            raise HTTPException(503, "serviço de autenticação indisponível") from None

    @app.get("/api/acesso/usuario")
    def usuario(usuario: Usuario):
        return {"email": usuario}

    # Cargas da planilha e dos RPAs (T16): mesmas regras e testes, ligadas ao usuário autenticado daqui.
    registrar_rotas_carga(
        app,
        cfg=cfg,
        repositorio=repositorio,
        processador=processador,
        usuario_atual=usuario_atual,
        mascarar_email=acesso.mascarar_email,
        agora=_agora,
    )

    def _relatorio(competencia: str):
        validar_competencia(competencia)
        df_ref = planilha_para_df(repositorio.listar_planilha(competencia))
        df_rpa = rpas_para_df(repositorio.listar_rpas(competencia))
        if df_ref.empty and df_rpa.empty:
            raise HTTPException(404, f"nenhum dado carregado para {competencia}")
        r = comparar(df_ref, df_rpa, competencia, cfg.tolerancia_centavos, agora=_agora())
        log.info(
            "comparacao",
            extra={"competencia": competencia, "documentos": r.qtd_documentos, "divergencias": r.qtd_divergencias},
        )
        return r

    @app.get("/api/relatorios/{competencia}")
    def relatorio(competencia: str, usuario: Usuario):
        return relatorio_para_dicionario(_relatorio(competencia))

    @app.get("/api/relatorios/{competencia}/exportar")
    def exportar(competencia: str, formato: str, usuario: Usuario):
        r = _relatorio(competencia)
        nome = f"validacao-rpa-{competencia}"
        if formato == "md":
            return Response(
                gerar_markdown(r),
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{nome}.md"'},
            )
        if formato == "pdf":
            return Response(
                gerar_pdf(r),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{nome}.pdf"'},
            )
        raise HTTPException(422, "formato deve ser 'pdf' ou 'md'")

    estaticos = Path(cfg.static_dir)
    if estaticos.is_dir():  # build do Vite; montado por último para não sombrear /api
        app.mount("/", StaticFiles(directory=estaticos, html=True), name="front")
    return app
