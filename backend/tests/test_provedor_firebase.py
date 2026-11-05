"""REST do Firebase Auth com transporte simulado (httpx.MockTransport) — sem rede, sem credenciais."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.autenticacao import CredenciaisInvalidas, ErroProvedorIdentidade, TokenInvalido
from app.provedor_firebase import ProvedorFirebase

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def provedor(responder):
    return ProvedorFirebase("chave-web", "projeto", httpx.Client(transport=httpx.MockTransport(responder)))


def erro(mensagem, status=400):
    return httpx.Response(status, json={"error": {"code": status, "message": mensagem}})


def test_login_ok_envia_chave_e_corpo_corretos():
    vistos = []

    def responder(req):
        vistos.append(req)
        return httpx.Response(200, json={"idToken": "id", "refreshToken": "rt", "expiresIn": "3600"})

    s = provedor(responder).entrar_com_senha("ana@empresa.com", "senha", T0)
    assert (s.id_token, s.refresh_token, s.expira_em) == ("id", "rt", T0 + timedelta(hours=1))
    assert vistos[0].url.host == "identitytoolkit.googleapis.com" and vistos[0].url.params["key"] == "chave-web"
    assert b'"returnSecureToken":true' in vistos[0].content.replace(b" ", b"")


@pytest.mark.parametrize(
    "mensagem",
    [
        "INVALID_LOGIN_CREDENTIALS",
        "EMAIL_NOT_FOUND",
        "USER_DISABLED",
        "TOO_MANY_ATTEMPTS_TRY_LATER : Access to this account has been disabled",
    ],
)
def test_login_erros_de_credencial(mensagem):
    with pytest.raises(CredenciaisInvalidas):
        provedor(lambda req: erro(mensagem)).entrar_com_senha("a@b.com", "x", T0)


def test_login_erro_inesperado_nao_e_credencial():
    with pytest.raises(ErroProvedorIdentidade):
        provedor(lambda req: erro("PROJECT_NOT_FOUND")).entrar_com_senha("a@b.com", "x", T0)
    with pytest.raises(ErroProvedorIdentidade):
        provedor(lambda req: httpx.Response(503, text="indisponível")).entrar_com_senha("a@b.com", "x", T0)


def test_renovar():
    ok = provedor(
        lambda req: httpx.Response(200, json={"id_token": "id2", "refresh_token": "rt2", "expires_in": "3600"})
    )
    assert ok.renovar_sessao("rt", T0).id_token == "id2"
    with pytest.raises(TokenInvalido):
        provedor(lambda req: erro("TOKEN_EXPIRED")).renovar_sessao("rt", T0)


def test_emulador_troca_a_url(monkeypatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    vistos = []

    def responder(req):
        vistos.append(str(req.url))
        return httpx.Response(200, json={"idToken": "id", "refreshToken": "rt", "expiresIn": "3600"})

    provedor(responder).entrar_com_senha("a@b.com", "x", T0)
    assert vistos[0].startswith("http://localhost:9099/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword")


def test_exige_chave():
    with pytest.raises(ValueError):
        ProvedorFirebase("")
