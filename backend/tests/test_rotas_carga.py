from datetime import UTC, datetime
from io import BytesIO

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.configuracao import Configuracao
from app.extracao.extrator_texto import ErroExtracao
from app.extracao.processamento import processar_rpa
from app.repositorio import RepositorioMemoria
from app.rotas_carga import registrar_rotas_carga
from tests.fixtures import textos_rpa as t
from tests.fixtures.planilhas import gerar_xlsx, linha

CFG = Configuracao(_env_file=None, max_upload_mb=1, max_arquivos_por_lote=10)
TEXTOS = {
    "13915419": t.A_IRRF_BRANCO,
    "14037118": t.A_INSS_COLADO,
    "14070887": t.B_LINHAS,
    "13809297": t.A_SEST_TRUNCADO,
    "14090502": t.A_INSS_DIVERGENTE,
    "14037076": t.A_ZERO_CURTO,
}
XLSX = ("Nova Lima.xlsx", gerar_xlsx(), "application/octet-stream")  # competência 2026-10, 6 RPAs


def processador_falso(conteudo: bytes, nome: str, competencia: str, modo: str):
    """Usa o conteúdo do upload como 'texto extraído': testa as rotas sem LibreOffice/Tesseract."""
    if conteudo == b"corrompido":
        raise ErroExtracao("falha na conversão")
    return processar_rpa(conteudo, nome, competencia, "native", nativo=lambda c, n: c.decode("utf-8"))


@pytest.fixture
def repo():
    return RepositorioMemoria()


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


def rpa(numero, texto=None):
    return ("arquivos", (f"RPA - X - {numero}.doc", (texto or TEXTOS[numero]).encode("utf-8"), "application/msword"))


def carregar_planilha(cliente, competencia="2026-10", arquivo=XLSX, **extra):
    return cliente.post("/api/planilhas", data={"competencia": competencia, **extra}, files={"arquivo": arquivo})


def carregar_rpas(cliente, arquivos, competencia="2026-10", **extra):
    return cliente.post("/api/rpas", data={"competencia": competencia, **extra}, files=arquivos)


def test_planilha_grava_e_devolve_o_resumo(cliente):
    r = carregar_planilha(cliente)
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["competencia"], corpo["competencia_arquivo"], corpo["erros_abas"]) == ("2026-10", "2026-10", [])
    assert corpo["abas"][0] == {
        "aba": "Planilha1",
        "codigo_empresa": "671",
        "cnpj": "14.429.795/0015-68",
        "competencia": "2026-10",
        "qtd_linhas": 6,
        "qtd_linhas_sem_recibo": 1,
    }
    situacao = cliente.get("/api/planilhas/2026-10").json()
    assert (situacao["carregada"], situacao["qtd_linhas"], situacao["empresas"]) == (True, 6, ["671"])
    assert cliente.get("/api/planilhas/2026-09").json()["carregada"] is False


def test_planilha_com_competencia_diferente_da_celula_pede_decisao_e_nao_grava(cliente):
    r = carregar_planilha(cliente, competencia="2026-11")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert (d["codigo"], d["competencia_arquivo"], d["competencia_informada"]) == (
        "competencia_divergente",
        "2026-10",
        "2026-11",
    )
    assert cliente.get("/api/planilhas/2026-10").json()["carregada"] is False


def test_planilha_prevalece_tela_ou_arquivo(cliente):
    assert carregar_planilha(cliente, competencia="2026-11", prevalece="tela").json()["competencia"] == "2026-11"
    assert carregar_planilha(cliente, competencia="2026-12", prevalece="arquivo").json()["competencia"] == "2026-10"
    assert carregar_planilha(cliente, prevalece="qualquer").status_code == 422


def test_planilha_nova_substitui_a_competencia_inteira(cliente):
    carregar_planilha(cliente)
    outra = gerar_xlsx({"Outra": ("672", [linha(1, "FULANO X", "15000001", 1000.0, 5.0, 22.0, 0)])})
    r = carregar_planilha(cliente, arquivo=("b.xlsx", outra, "application/octet-stream")).json()
    assert r["qtd_linhas_substituidas"] == 6
    situacao = cliente.get("/api/planilhas/2026-10").json()
    assert (situacao["qtd_linhas"], situacao["empresas"]) == (1, ["672"])


def test_planilha_aba_sem_codigo_e_listada_e_as_outras_carregam(cliente):
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx({"Boa": ("671", []), "Ruim": ("672", [])})))
    wb["Ruim"]["E1"] = None
    buf = BytesIO()
    wb.save(buf)
    r = carregar_planilha(cliente, arquivo=("p.xlsx", buf.getvalue(), "application/octet-stream"))
    assert r.status_code == 200
    assert [a["aba"] for a in r.json()["abas"]] == ["Boa"]
    assert [e["aba"] for e in r.json()["erros_abas"]] == ["Ruim"]


def test_planilha_invalida_e_formato_errado(cliente):
    assert carregar_planilha(cliente, arquivo=("x.xlsx", b"nao e xlsx", "application/octet-stream")).status_code == 422
    assert carregar_planilha(cliente, arquivo=("x.csv", b"a,b", "text/csv")).status_code == 415
    assert carregar_planilha(cliente, competencia="10/2026").status_code == 422


def test_rpas_exigem_planilha_na_competencia(cliente):
    r = carregar_rpas(cliente, [rpa("13915419")])
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "sem_planilha"


def test_rpas_carga_complementar_nao_reprocessa_o_que_ja_existe(cliente, repo):
    carregar_planilha(cliente)
    primeira = carregar_rpas(cliente, [rpa("13915419"), rpa("14037118")]).json()
    assert (primeira["ok"], primeira["erros"], primeira["ja_carregados"]) == (2, 0, 0)

    segunda = carregar_rpas(cliente, [rpa("13915419"), rpa("14070887")]).json()
    assert [(x["numero_rpa"], x["status"]) for x in segunda["resultados"]] == [
        ("13915419", "ja_carregado"),
        ("14070887", "ok"),
    ]
    assert repo.numeros_rpas("2026-10") == {"13915419", "14037118", "14070887"}


def test_rpas_substituir_reprocessa(cliente, repo):
    carregar_planilha(cliente)
    carregar_rpas(cliente, [rpa("14090502", t.A_INSS_DIVERGENTE)])
    antes = repo.listar_rpas("2026-10")[0].inss
    corrigido = rpa("14090502", t.A_INSS_COLADO.replace("14037118", "14090502"))
    r = carregar_rpas(cliente, [corrigido], substituir="true").json()
    assert r["resultados"][0]["status"] == "ok"
    assert repo.listar_rpas("2026-10")[0].inss != antes


def test_rpas_erros_por_arquivo_nao_derrubam_o_lote(cliente):
    carregar_planilha(cliente)
    arquivos = [
        rpa("13915419"),
        rpa("13915419"),  # repetido no envio
        ("arquivos", ("RPA sem numero.doc", TEXTOS["13915419"].encode(), "application/msword")),
        ("arquivos", ("RPA - X - 13915420.pdf", b"x", "application/pdf")),
        ("arquivos", ("RPA - X - 13915421.doc", b"corrompido", "application/msword")),
        ("arquivos", ("RPA - X - 13915422.doc", b"x" * (1024 * 1024 + 1), "application/msword")),
    ]
    r = carregar_rpas(cliente, arquivos).json()
    assert [x["status"] for x in r["resultados"]] == ["ok", "erro", "erro", "erro", "erro", "erro"]
    assert "repetido" in r["resultados"][1]["erro"]
    assert "1 MB" in r["resultados"][5]["erro"]
    assert (r["ok"], r["erros"]) == (1, 5)


def test_rpas_limites_e_competencia(cliente):
    carregar_planilha(cliente)
    muitos = [rpa("13915419")] * 11
    assert carregar_rpas(cliente, muitos).status_code == 413
    assert carregar_rpas(cliente, [rpa("13915419")], competencia="10/2026").status_code == 422


def test_verificacao_usa_so_os_nomes_e_confere_com_a_planilha(cliente):
    sem_planilha = cliente.post(
        "/api/rpas/verificacao", json={"competencia": "2026-10", "arquivos": ["RPA - X - 13915419.doc"]}
    ).json()
    assert (sem_planilha["planilha_carregada"], sem_planilha["confere"]) == (False, False)

    carregar_planilha(cliente)
    carregar_rpas(cliente, [rpa("13915419")])
    nomes = [f"RPA - X - {n}.doc" for n in TEXTOS]
    v = cliente.post("/api/rpas/verificacao", json={"competencia": "2026-10", "arquivos": nomes}).json()
    assert (v["qtd_linhas_planilha"], v["qtd_ja_carregados"], v["qtd_ja_existentes_no_envio"], v["qtd_novos"]) == (
        6,
        1,
        1,
        5,
    )
    assert (v["qtd_total_apos_envio"], v["diferenca"], v["confere"]) == (6, 0, True)
    assert cliente.post("/api/rpas/verificacao", json={"competencia": "x", "arquivos": []}).status_code == 422
