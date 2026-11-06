"""Implementação real do ProvedorIdentidade: REST do Firebase Auth para login/renovação e Admin SDK para validar."""

import os
from datetime import datetime, timedelta

import httpx
from firebase_admin import exceptions

from app.autenticacao import CredenciaisInvalidas, ErroProvedorIdentidade, SessaoAcesso, TokenInvalido

ERROS_CREDENCIAL = frozenset(
    {
        "EMAIL_NOT_FOUND",
        "INVALID_PASSWORD",
        "INVALID_LOGIN_CREDENTIALS",
        "USER_DISABLED",
        "INVALID_EMAIL",
        "MISSING_PASSWORD",
        "TOO_MANY_ATTEMPTS_TRY_LATER",
    }
)


def _codigo_erro(r: httpx.Response) -> str:
    try:
        return r.json()["error"]["message"].split(" ")[0].split(":")[0]
    except (ValueError, KeyError, TypeError, AttributeError):
        return f"HTTP_{r.status_code}"


class ProvedorFirebase:
    def __init__(self, api_key: str, projeto: str | None = None, cliente_http: httpx.Client | None = None):
        if not api_key:
            raise ValueError("FIREBASE_WEB_API_KEY ausente")
        self._api_key, self._projeto = api_key, projeto
        self._http = cliente_http or httpx.Client(timeout=10)
        emulador = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")  # também é lido pelo Admin SDK
        prefixo = f"http://{emulador}/" if emulador else "https://"
        self._url_login = f"{prefixo}identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        self._url_token = f"{prefixo}securetoken.googleapis.com/v1/token"
        self._admin = None

    def _auth_admin(self):
        if self._admin is None:  # inicialização tardia: os testes de REST não precisam de credenciais do Google
            import firebase_admin
            from firebase_admin import auth

            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": self._projeto} if self._projeto else None)
            self._admin = auth
        return self._admin

    def entrar_com_senha(self, email: str, senha: str, agora: datetime) -> SessaoAcesso:
        try:
            r = self._http.post(
                self._url_login,
                params={"key": self._api_key},
                json={"email": email, "password": senha, "returnSecureToken": True},
            )
        except httpx.HTTPError as e:
            raise ErroProvedorIdentidade(str(e)) from e
        if r.status_code == 200:
            try:
                d = r.json()
                return SessaoAcesso(d["idToken"], d["refreshToken"], agora + timedelta(seconds=int(d["expiresIn"])))
            except (ValueError, KeyError, TypeError) as e:
                raise ErroProvedorIdentidade("resposta inesperada do login") from e
        codigo = _codigo_erro(r)
        if codigo in ERROS_CREDENCIAL:
            raise CredenciaisInvalidas()
        raise ErroProvedorIdentidade(codigo)

    def renovar_sessao(self, refresh_token: str, agora: datetime) -> SessaoAcesso:
        try:
            r = self._http.post(
                self._url_token,
                params={"key": self._api_key},
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
        except httpx.HTTPError as e:
            raise ErroProvedorIdentidade(str(e)) from e
        if r.status_code == 200:
            try:
                d = r.json()
                return SessaoAcesso(d["id_token"], d["refresh_token"], agora + timedelta(seconds=int(d["expires_in"])))
            except (ValueError, KeyError, TypeError) as e:
                raise ErroProvedorIdentidade("resposta inesperada da renovação") from e
        if r.status_code in (400, 401, 403):
            raise TokenInvalido(_codigo_erro(r))
        raise ErroProvedorIdentidade(_codigo_erro(r))

    def verificar_token(self, id_token: str) -> dict:
        auth = self._auth_admin()
        try:
            return auth.verify_id_token(id_token, check_revoked=True)
        except auth.CertificateFetchError as e:
            raise ErroProvedorIdentidade(str(e)) from e
        except (ValueError, auth.InvalidIdTokenError, auth.UserDisabledError, auth.UserNotFoundError) as e:
            raise TokenInvalido(str(e)) from e  # inclui usuário apagado com token ainda válido
        except exceptions.FirebaseError as e:  # falha ao consultar a revogação (rede, serviço)
            raise ErroProvedorIdentidade(str(e)) from e
