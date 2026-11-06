"""Carga manual de acessos — ÚNICA forma de autorizar alguém (D1).

Lê uma lista de e-mails, cria no Firebase Auth quem não existe, grava o custom claim de acesso e, opcionalmente,
remove o acesso de quem saiu da lista (revogando as sessões abertas). Não há cadastro pela aplicação.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class UsuarioAcesso:
    uid: str
    email: str


class AdministradorAcessos(Protocol):
    def obter_por_email(self, email: str) -> UsuarioAcesso | None: ...
    def criar(self, email: str) -> UsuarioAcesso: ...
    def definir_autorizacao(self, uid: str, autorizado: bool) -> None: ...
    def revogar_sessoes(self, uid: str) -> None: ...
    def listar_autorizados(self) -> list[UsuarioAcesso]: ...
    def gerar_link_definicao_senha(self, email: str) -> str: ...


@dataclass
class ResultadoCarga:
    criados: list[str] = field(default_factory=list)
    autorizados: list[str] = field(default_factory=list)
    ja_autorizados: list[str] = field(default_factory=list)
    removidos: list[str] = field(default_factory=list)
    links_definicao_senha: dict[str, str] = field(default_factory=dict)


def ler_lista_emails(texto: str) -> tuple[list[str], list[str]]:
    """Um e-mail por linha (vírgula/ponto e vírgula também valem); '#' inicia comentário. -> (válidos, inválidos)"""
    validos: list[str] = []
    invalidos: list[str] = []
    for linha in texto.splitlines():
        for item in re.split(r"[;,]", linha.split("#", 1)[0]):
            email = item.strip().lower()
            if not email:
                continue
            if not _EMAIL.match(email):
                invalidos.append(item.strip())
            elif email not in validos:
                validos.append(email)
    return validos, invalidos


def sincronizar_acessos(
    emails: list[str], admin: AdministradorAcessos, *, remover_ausentes: bool = False, simular: bool = False
) -> ResultadoCarga:
    r = ResultadoCarga()
    ja = {u.email.lower(): u for u in admin.listar_autorizados()}
    for email in emails:
        if email in ja:
            r.ja_autorizados.append(email)
            continue
        usuario = admin.obter_por_email(email)
        if usuario is None:
            r.criados.append(email)
            if not simular:
                usuario = admin.criar(email)
                r.links_definicao_senha[email] = admin.gerar_link_definicao_senha(email)
        r.autorizados.append(email)
        if not simular:
            admin.definir_autorizacao(usuario.uid, True)
    if remover_ausentes:
        for email, usuario in sorted(ja.items()):
            if email not in emails:
                r.removidos.append(email)
                if not simular:
                    admin.definir_autorizacao(usuario.uid, False)
                    admin.revogar_sessoes(usuario.uid)
    return r


class AdministradorFirebase:
    """Implementação real com o Admin SDK. Exige credencial com papel 'Firebase Authentication Admin'."""

    def __init__(self, claim: str = "rpa_autorizado", projeto: str | None = None):
        import firebase_admin
        from firebase_admin import auth

        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": projeto} if projeto else None)
        self._auth, self._claim = auth, claim

    def obter_por_email(self, email):
        try:
            u = self._auth.get_user_by_email(email)
        except self._auth.UserNotFoundError:
            return None
        return UsuarioAcesso(u.uid, u.email)

    def criar(self, email):
        u = self._auth.create_user(email=email, email_verified=False)
        return UsuarioAcesso(u.uid, u.email)

    def definir_autorizacao(self, uid, autorizado):
        claims = dict(self._auth.get_user(uid).custom_claims or {})
        if autorizado:
            claims[self._claim] = True
        else:
            claims.pop(self._claim, None)
        self._auth.set_custom_user_claims(uid, claims or None)

    def revogar_sessoes(self, uid):
        self._auth.revoke_refresh_tokens(uid)

    def listar_autorizados(self):
        return [
            UsuarioAcesso(u.uid, u.email)
            for u in self._auth.list_users().iterate_all()
            if (u.custom_claims or {}).get(self._claim) is True
        ]

    def gerar_link_definicao_senha(self, email):
        return self._auth.generate_password_reset_link(email)
