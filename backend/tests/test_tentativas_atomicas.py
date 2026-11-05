"""A6: o contador de tentativas de login não pode perder contagem sob requisições paralelas."""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.autenticacao import CredenciaisInvalidas, LoginBloqueado, autenticar, chave_tentativas
from app.configuracao import Configuracao
from app.repositorio import RepositorioFirestore, RepositorioMemoria, TentativasLogin
from tests.fixtures.provedor_falso import ProvedorFalso

AGORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def somar(t: TentativasLogin | None) -> TentativasLogin:
    time.sleep(0.002)  # alarga a janela da corrida: sem trava/transação, contagens se perdem
    return TentativasLogin((t.falhas if t else 0) + 1, AGORA, None)


def test_atualizar_tentativas_nao_perde_contagem_em_memoria():
    repo = RepositorioMemoria()
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda _: repo.atualizar_tentativas("k", somar), range(100)))
    assert repo.obter_tentativas("k").falhas == 100


def test_atualizar_tentativas_devolve_o_novo_valor():
    repo = RepositorioMemoria()
    assert repo.atualizar_tentativas("k", somar).falhas == 1
    assert repo.atualizar_tentativas("k", somar).falhas == 2


def test_logins_errados_em_paralelo_contam_todos():
    class ProvedorLento(ProvedorFalso):
        def entrar_com_senha(self, email, senha, agora):
            time.sleep(0.002)
            return super().entrar_com_senha(email, senha, agora)

    cfg = Configuracao(_env_file=None, firebase_web_api_key="k", login_max_attempts=1000)
    repo, prov = RepositorioMemoria(), ProvedorLento({"ana@empresa.com": "certa"}, {"ana@empresa.com"})

    def tentar(_):
        with pytest.raises((CredenciaisInvalidas, LoginBloqueado)):
            autenticar("ana@empresa.com", "errada", cfg, repo, prov, AGORA)

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(tentar, range(64)))
    assert repo.obter_tentativas(chave_tentativas("ana@empresa.com")).falhas == 64


@pytest.mark.integracao
@pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="emulador do Firestore não configurado")
def test_atualizar_tentativas_e_transacional_no_firestore_emulador():
    repo = RepositorioFirestore(project=f"teste-{uuid.uuid4().hex[:8]}")
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda _: repo.atualizar_tentativas("k", somar), range(12)))
    assert repo.obter_tentativas("k").falhas == 12
