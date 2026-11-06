"""A1 e A3: logs só com contagens e falha do repositório que não derruba o lote."""

import logging
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.configuracao import Configuracao
from app.extracao.processamento import processar_rpa
from app.repositorio import RepositorioMemoria
from app.rotas_carga import registrar_rotas_carga
from tests.fixtures import textos_rpa as t
from tests.fixtures.planilhas import gerar_xlsx

CFG = Configuracao(_env_file=None, max_upload_mb=1, max_arquivos_por_lote=10)
TEXTOS = {"13915419": t.A_IRRF_BRANCO, "14037118": t.A_INSS_COLADO, "14070887": t.B_LINHAS}


def processador_falso(conteudo, nome, competencia, modo):
    return processar_rpa(conteudo, nome, competencia, "native", nativo=lambda c, n: c.decode("utf-8"))


class RepositorioQueFalhaNoSegundoRpa(RepositorioMemoria):
    def __init__(self):
        super().__init__()
        self.chamadas = 0

    def salvar_rpa(self, rpa, *, usuario, agora):
        self.chamadas += 1
        if self.chamadas == 2:
            raise RuntimeError("falha inesperada com dado sensível FULANO")
        super().salvar_rpa(rpa, usuario=usuario, agora=agora)


@pytest.fixture
def repo():
    return RepositorioQueFalhaNoSegundoRpa()


@pytest.fixture
def cliente(repo):
    app = FastAPI()
    registrar_rotas_carga(
        app,
        cfg=CFG,
        repositorio=repo,
        processador=processador_falso,
        usuario_atual=lambda: "ana@empresa.com",
        mascarar_email=lambda e: "an***@empresa.com",
        agora=lambda: datetime(2026, 11, 4, 15, 0, tzinfo=UTC),
    )
    return TestClient(app)


def planilha(cliente):
    return cliente.post(
        "/api/planilhas",
        data={"competencia": "2026-10"},
        files={"arquivo": ("Nova Lima.xlsx", gerar_xlsx(), "application/octet-stream")},
    )


def test_log_da_planilha_tem_so_contagens(cliente, caplog):
    with caplog.at_level(logging.INFO, logger="rpa"):
        assert planilha(cliente).status_code == 200
    evento = next(r for r in caplog.records if r.getMessage() == "planilha_carregada")
    assert evento.qtd_abas == 1 and not hasattr(evento, "abas")
    assert "14.429.795" not in str(evento.__dict__) and "671" not in str(evento.qtd_abas)


def test_falha_do_repositorio_no_meio_do_lote_nao_derruba_os_outros(cliente, caplog):
    planilha(cliente)
    arquivos = [
        ("arquivos", (f"RPA - X - {n}.doc", txt.encode("utf-8"), "application/msword")) for n, txt in TEXTOS.items()
    ]
    with caplog.at_level(logging.INFO, logger="rpa"):
        r = cliente.post("/api/rpas", data={"competencia": "2026-10"}, files=arquivos)
    corpo = r.json()
    assert r.status_code == 200
    assert [x["status"] for x in corpo["resultados"]] == ["ok", "erro", "ok"]
    assert corpo["resultados"][1]["erro"] == "falha ao gravar"
    assert (corpo["ok"], corpo["erros"]) == (2, 1)
    assert "FULANO" not in caplog.text and "14037118" not in caplog.text  # nem mensagem nem nome de arquivo no log
