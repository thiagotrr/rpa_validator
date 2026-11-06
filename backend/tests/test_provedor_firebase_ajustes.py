"""A4 e A5: o provedor real nunca deixa escapar exceção solta (viraria 500)."""

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from firebase_admin import auth, exceptions

from app.autenticacao import ErroProvedorIdentidade, TokenInvalido
from app.provedor_firebase import ProvedorFirebase

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def provedor_com_admin(erro: Exception) -> ProvedorFirebase:
    """Admin SDK simulado: usa as classes de exceção reais e levanta `erro` ao verificar o token."""

    def verificar(token, check_revoked=False):
        raise erro

    falso = SimpleNamespace(
        verify_id_token=verificar,
        CertificateFetchError=auth.CertificateFetchError,
        InvalidIdTokenError=auth.InvalidIdTokenError,
        UserDisabledError=auth.UserDisabledError,
        UserNotFoundError=auth.UserNotFoundError,
    )
    p = ProvedorFirebase("chave", "projeto")
    p._admin = falso
    return p


def test_token_de_usuario_apagado_vira_token_invalido():
    with pytest.raises(TokenInvalido):
        provedor_com_admin(auth.UserNotFoundError("sumiu")).verificar_token("t")


def test_falha_de_rede_do_admin_sdk_vira_erro_do_provedor():
    with pytest.raises(ErroProvedorIdentidade):
        provedor_com_admin(exceptions.UnavailableError("sem rede")).verificar_token("t")


def test_token_expirado_ou_revogado_continua_token_invalido():
    with pytest.raises(TokenInvalido):
        provedor_com_admin(auth.ExpiredIdTokenError("expirou", None)).verificar_token("t")
    with pytest.raises(TokenInvalido):
        provedor_com_admin(auth.RevokedIdTokenError("revogado")).verificar_token("t")


def provedor_rest(resposta: httpx.Response) -> ProvedorFirebase:
    return ProvedorFirebase("chave", "projeto", httpx.Client(transport=httpx.MockTransport(lambda req: resposta)))


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="não é json"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"idToken": "a", "refreshToken": "b", "expiresIn": "abc"}),
    ],
)
def test_login_com_200_malformado_vira_erro_do_provedor(resposta):
    with pytest.raises(ErroProvedorIdentidade):
        provedor_rest(resposta).entrar_com_senha("a@b.com", "x", T0)


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="não é json"),
        httpx.Response(200, json={"id_token": "a"}),
        httpx.Response(200, json={"id_token": "a", "refresh_token": "b", "expires_in": None}),
    ],
)
def test_renovacao_com_200_malformado_vira_erro_do_provedor(resposta):
    with pytest.raises(ErroProvedorIdentidade):
        provedor_rest(resposta).renovar_sessao("rt", T0)
