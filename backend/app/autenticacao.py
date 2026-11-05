"""Acesso via Firebase Auth, intermediado pelo backend.

O front-end nunca fala direto com o Firebase: o backend faz o login (e conta as falhas — limite de N tentativas
seguidas por janela), devolve o ID token do Firebase (JWT RS256) e valida esse token em toda chamada. Só entra
quem tem o custom claim de acesso, gravado exclusivamente pela carga manual de acessos (app.acessos).
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.configuracao import Configuracao
from app.repositorio import Repositorio, TentativasLogin


class CredenciaisInvalidas(Exception):
    pass


class LoginBloqueado(Exception):
    def __init__(self, ate: datetime):
        super().__init__(f"bloqueado até {ate.isoformat()}")
        self.ate = ate


class TokenInvalido(Exception):
    pass


class ErroProvedorIdentidade(Exception):
    """Firebase indisponível ou resposta inesperada — não conta como tentativa do usuário."""


@dataclass(frozen=True)
class SessaoAcesso:
    id_token: str
    refresh_token: str
    expira_em: datetime


class ProvedorIdentidade(Protocol):
    def entrar_com_senha(self, email: str, senha: str, agora: datetime) -> SessaoAcesso: ...
    def renovar_sessao(self, refresh_token: str, agora: datetime) -> SessaoAcesso: ...
    def verificar_token(self, id_token: str) -> dict: ...


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def chave_tentativas(email: str) -> str:
    """O documento de tentativas não guarda o e-mail em claro."""
    return hashlib.sha256(normalizar_email(email).encode()).hexdigest()


def mascarar_email(email: str) -> str:
    usuario, _, dominio = normalizar_email(email).partition("@")
    return f"{usuario[:2]}***@{dominio}" if dominio else "***"


def validar_token(id_token: str, cfg: Configuracao, provedor: ProvedorIdentidade) -> str:
    """-> e-mail do usuário. Exige o claim de acesso (sem ele, o usuário do Firebase não entra)."""
    dados = provedor.verificar_token(id_token)
    if dados.get(cfg.claim_acesso) is not True:
        raise TokenInvalido("usuário sem acesso autorizado")
    return normalizar_email(dados.get("email", ""))


def autenticar(
    email: str, senha: str, cfg: Configuracao, repo: Repositorio, provedor: ProvedorIdentidade, agora: datetime
) -> SessaoAcesso:
    chave = chave_tentativas(email)
    janela = timedelta(minutes=cfg.login_window_minutes)
    t = repo.obter_tentativas(chave)
    if t and t.bloqueado_ate and agora < t.bloqueado_ate:
        raise LoginBloqueado(t.bloqueado_ate)

    try:
        sessao = provedor.entrar_com_senha(normalizar_email(email), senha, agora)
        validar_token(sessao.id_token, cfg, provedor)  # senha certa mas sem claim = mesma resposta de senha errada
    except (CredenciaisInvalidas, TokenInvalido):
        expirou = t is None or (agora - t.primeira_falha) > janela or (t.bloqueado_ate and agora >= t.bloqueado_ate)
        base = TentativasLogin(0, agora, None) if expirou else t
        falhas = base.falhas + 1
        bloqueio = agora + janela if falhas >= cfg.login_max_attempts else None
        repo.salvar_tentativas(chave, TentativasLogin(falhas, base.primeira_falha, bloqueio))
        if bloqueio:
            raise LoginBloqueado(bloqueio) from None
        raise CredenciaisInvalidas() from None

    repo.limpar_tentativas(chave)
    return sessao


def renovar(refresh_token: str, cfg: Configuracao, provedor: ProvedorIdentidade, agora: datetime) -> SessaoAcesso:
    sessao = provedor.renovar_sessao(refresh_token, agora)
    validar_token(sessao.id_token, cfg, provedor)  # acesso removido -> renovação recusada
    return sessao
