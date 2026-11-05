from datetime import UTC, datetime, timedelta

import pytest

from app.autenticacao import (
    CredenciaisInvalidas,
    LoginBloqueado,
    TokenInvalido,
    autenticar,
    chave_tentativas,
    mascarar_email,
    renovar,
    validar_token,
)
from app.configuracao import Configuracao
from app.repositorio import RepositorioMemoria
from tests.fixtures.provedor_falso import ProvedorFalso

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
CFG = Configuracao(_env_file=None, firebase_web_api_key="k", login_max_attempts=5, login_window_minutes=15)


def provedor():
    return ProvedorFalso({"ana@empresa.com": "senha-ana", "sem.claim@empresa.com": "senha-x"}, {"ana@empresa.com"})


def falhar(repo, prov, n, email="ana@empresa.com", agora=T0):
    for i in range(n):
        with pytest.raises((CredenciaisInvalidas, LoginBloqueado)):
            autenticar(email, "errada", CFG, repo, prov, agora + timedelta(seconds=i))


def test_login_valido_devolve_sessao_e_email_normalizado():
    s = autenticar("  ANA@empresa.com ", "senha-ana", CFG, RepositorioMemoria(), provedor(), T0)
    assert s.expira_em == T0 + timedelta(hours=1)
    assert validar_token(s.id_token, CFG, provedor()) == "ana@empresa.com"


def test_usuario_sem_claim_tem_a_mesma_resposta_de_senha_errada_e_conta_falha():
    repo, prov = RepositorioMemoria(), provedor()
    with pytest.raises(CredenciaisInvalidas):
        autenticar("sem.claim@empresa.com", "senha-x", CFG, repo, prov, T0)
    with pytest.raises(CredenciaisInvalidas):
        autenticar("ninguem@x.com", "qualquer", CFG, repo, prov, T0)
    assert repo.obter_tentativas(chave_tentativas("sem.claim@empresa.com")).falhas == 1


def test_quinta_falha_seguida_bloqueia_ate_fim_da_janela_mesmo_com_senha_certa():
    repo, prov = RepositorioMemoria(), provedor()
    falhar(repo, prov, 4)
    with pytest.raises(LoginBloqueado) as e:
        autenticar("ana@empresa.com", "errada", CFG, repo, prov, T0 + timedelta(seconds=10))
    assert e.value.ate == T0 + timedelta(seconds=10, minutes=15)
    with pytest.raises(LoginBloqueado):
        autenticar("ana@empresa.com", "senha-ana", CFG, repo, prov, T0 + timedelta(minutes=5))
    autenticar("ana@empresa.com", "senha-ana", CFG, repo, prov, T0 + timedelta(minutes=16))


def test_sucesso_zera_contador_e_falhas_fora_da_janela_nao_acumulam():
    repo, prov = RepositorioMemoria(), provedor()
    falhar(repo, prov, 4)
    autenticar("ana@empresa.com", "senha-ana", CFG, repo, prov, T0 + timedelta(minutes=1))
    falhar(repo, prov, 4, agora=T0 + timedelta(minutes=2))
    falhar(repo, prov, 1, agora=T0 + timedelta(minutes=30))
    assert repo.obter_tentativas(chave_tentativas("ana@empresa.com")).falhas == 1


def test_limite_e_janela_parametrizaveis():
    repo, prov = RepositorioMemoria(), provedor()
    cfg = CFG.model_copy(update={"login_max_attempts": 2})
    with pytest.raises(CredenciaisInvalidas):
        autenticar("ana@empresa.com", "x", cfg, repo, prov, T0)
    with pytest.raises(LoginBloqueado):
        autenticar("ana@empresa.com", "x", cfg, repo, prov, T0)


def test_validar_token_exige_claim_e_token_valido():
    prov = provedor()
    s = autenticar("ana@empresa.com", "senha-ana", CFG, RepositorioMemoria(), prov, T0)
    prov.autorizados.clear()  # acesso removido pela carga manual
    with pytest.raises(TokenInvalido):
        validar_token(s.id_token, CFG, prov)
    with pytest.raises(TokenInvalido):
        validar_token("lixo", CFG, prov)


def test_renovar_recusa_quem_perdeu_o_acesso():
    prov = provedor()
    s = autenticar("ana@empresa.com", "senha-ana", CFG, RepositorioMemoria(), prov, T0)
    assert renovar(s.refresh_token, CFG, prov, T0 + timedelta(minutes=50)).expira_em == T0 + timedelta(minutes=110)
    prov.revogados.add("ana@empresa.com")
    with pytest.raises(TokenInvalido):
        renovar(s.refresh_token, CFG, prov, T0 + timedelta(minutes=51))


def test_mascarar_email():
    assert mascarar_email("Thiago@Empresa.com") == "th***@empresa.com"
    assert mascarar_email("semarroba") == "***"
