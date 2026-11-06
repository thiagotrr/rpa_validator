import pytest
from fastapi.testclient import TestClient

from app.aplicacao import criar_aplicacao
from app.configuracao import Configuracao
from app.extracao.extrator_texto import ErroExtracao
from app.extracao.processamento import processar_rpa
from app.repositorio import RepositorioMemoria
from tests.fixtures import textos_rpa as t
from tests.fixtures.planilhas import gerar_xlsx
from tests.fixtures.provedor_falso import ProvedorFalso

CFG = Configuracao(
    _env_file=None,
    firebase_web_api_key="k",
    repository_backend="memory",
    static_dir="nao-existe",
    max_upload_mb=1,
    max_arquivos_por_lote=10,
    tolerancia_centavos=0,
)
TEXTOS = {
    "13915419": t.A_IRRF_BRANCO,
    "14037118": t.A_INSS_COLADO,
    "14070887": t.B_LINHAS,
    "13809297": t.A_SEST_TRUNCADO,
    "14090502": t.A_INSS_DIVERGENTE,
    "14037076": t.A_ZERO_CURTO,
}


def processador_falso(conteudo: bytes, nome: str, competencia: str, modo: str):
    """Usa o conteúdo do upload como 'texto extraído' — testa a API sem LibreOffice/Tesseract."""
    if conteudo == b"corrompido":
        raise ErroExtracao("falha na conversão")
    return processar_rpa(conteudo, nome, competencia, "native", nativo=lambda c, n: c.decode("utf-8"))


def novo_cliente(cfg=CFG):
    prov = ProvedorFalso({"ana@empresa.com": "senha-ana"}, {"ana@empresa.com"})
    return TestClient(criar_aplicacao(cfg, RepositorioMemoria(), prov, processador_falso)), prov


@pytest.fixture
def cliente():
    return novo_cliente()[0]


def entrar(cliente) -> dict:
    r = cliente.post("/api/acesso/entrar", json={"email": "ana@empresa.com", "senha": "senha-ana"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['id_token']}"}


def carregar_tudo(cliente, h):
    """Planilha de out/2026 (6 RPAs) e os 6 RPAs correspondentes."""
    r = cliente.post(
        "/api/planilhas",
        headers=h,
        data={"competencia": "2026-10"},
        files={"arquivo": ("Nova Lima.xlsx", gerar_xlsx(), "application/octet-stream")},
    )
    assert r.status_code == 200
    arquivos = [
        ("arquivos", (f"RPA - X - {n}.doc", txt.encode("utf-8"), "application/msword")) for n, txt in TEXTOS.items()
    ]
    return r, cliente.post("/api/rpas", headers=h, data={"competencia": "2026-10"}, files=arquivos)


def test_aplicacao_recusa_subir_sem_chave_do_firebase():
    with pytest.raises(ValueError, match="FIREBASE_WEB_API_KEY"):
        criar_aplicacao(CFG.model_copy(update={"firebase_web_api_key": ""}), RepositorioMemoria())


def test_rotas_exigem_token(cliente):
    assert cliente.get("/healthz").status_code == 200
    assert cliente.get("/api/acesso/usuario").status_code == 401
    assert cliente.get("/api/relatorios/2026-10", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert cliente.get("/api/planilhas/2026-10").status_code == 401  # rotas de carga também
    assert cliente.post("/api/rpas/verificacao", json={"competencia": "2026-10", "arquivos": []}).status_code == 401
    assert cliente.get("/api/acesso/usuario", headers=entrar(cliente)).json() == {"email": "ana@empresa.com"}


def test_bloqueia_na_quinta_falha(cliente):
    for _ in range(4):
        assert cliente.post("/api/acesso/entrar", json={"email": "ana@empresa.com", "senha": "x"}).status_code == 401
    r = cliente.post("/api/acesso/entrar", json={"email": "ana@empresa.com", "senha": "x"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert (
        cliente.post("/api/acesso/entrar", json={"email": "ana@empresa.com", "senha": "senha-ana"}).status_code == 429
    )


def test_renovar_sessao_e_acesso_revogado():
    cliente, prov = novo_cliente()
    sessao = cliente.post("/api/acesso/entrar", json={"email": "ana@empresa.com", "senha": "senha-ana"}).json()
    r = cliente.post("/api/acesso/renovar", json={"refresh_token": sessao["refresh_token"]})
    assert r.status_code == 200 and r.json()["id_token"].startswith("id:ana@empresa.com")
    prov.autorizados.clear()
    assert cliente.post("/api/acesso/renovar", json={"refresh_token": sessao["refresh_token"]}).status_code == 401
    assert (
        cliente.get("/api/acesso/usuario", headers={"Authorization": f"Bearer {sessao['id_token']}"}).status_code == 401
    )


def test_fluxo_completo_carga_comparacao_exportacao(cliente):
    h = entrar(cliente)
    r_planilha, r_rpas = carregar_tudo(cliente, h)
    assert r_planilha.json()["abas"][0] == {
        "aba": "Planilha1",
        "codigo_empresa": "671",
        "cnpj": "14.429.795/0015-68",
        "competencia": "2026-10",
        "qtd_linhas": 6,
        "qtd_linhas_sem_recibo": 1,
    }
    assert (r_rpas.json()["ok"], r_rpas.json()["erros"]) == (6, 0)

    rel = cliente.get("/api/relatorios/2026-10", headers=h).json()
    assert rel["qtd_documentos"] == 6 and rel["qtd_divergencias"] == 2 and rel["tolerancia_centavos"] == 0
    assert rel["divergencias_por_campo"] == {"inss": 1, "sest_senat": 1}
    assert rel["divergencias"][1]["nome"] == "FULANO D**** DE M***"

    md = cliente.get("/api/relatorios/2026-10/exportar?formato=md", headers=h)
    assert md.headers["content-disposition"] == 'attachment; filename="validacao-rpa-2026-10.md"'
    assert "R$ 86,81" in md.text and "DELTA" not in md.text
    pdf = cliente.get("/api/relatorios/2026-10/exportar?formato=pdf", headers=h)
    assert pdf.content.startswith(b"%PDF")
    assert cliente.get("/api/relatorios/2026-10/exportar?formato=html", headers=h).status_code == 422  # sem HTML
    assert cliente.get("/api/relatorios/2026-10/exportar?formato=docx", headers=h).status_code == 422


def test_planilha_nova_mantem_os_rpas_ja_carregados_na_nova_validacao(cliente):
    h = entrar(cliente)
    carregar_tudo(cliente, h)
    cliente.post(  # mesma competência de novo: substitui a planilha, os RPAs continuam
        "/api/planilhas",
        headers=h,
        data={"competencia": "2026-10"},
        files={"arquivo": ("Nova Lima.xlsx", gerar_xlsx(), "application/octet-stream")},
    )
    rel = cliente.get("/api/relatorios/2026-10", headers=h).json()
    assert rel["qtd_documentos"] == 6 and rel["qtd_linhas_referencia"] == 6


def test_tolerancia_padrao_ignora_os_centavos():
    cliente, _ = novo_cliente(CFG.model_copy(update={"tolerancia_centavos": 2}))
    h = entrar(cliente)
    carregar_tudo(cliente, h)
    assert cliente.get("/api/relatorios/2026-10", headers=h).json()["qtd_divergencias"] == 0


def test_competencia_invalida_e_sem_dados(cliente):
    h = entrar(cliente)
    assert cliente.get("/api/relatorios/2026-13", headers=h).status_code == 422
    assert cliente.get("/api/relatorios/2026-09", headers=h).status_code == 404


def test_a2_corpo_acima_do_limite_e_recusado_antes_de_ler(cliente):
    h = entrar(cliente)
    grande = b"x" * (3 * 1024 * 1024)  # limite da planilha: 1 MB + margem de 1 MB
    r = cliente.post(
        "/api/planilhas",
        headers=h,
        data={"competencia": "2026-10"},
        files={"arquivo": ("grande.xlsx", grande, "application/octet-stream")},
    )
    assert r.status_code == 413
    enorme = b"x" * (12 * 1024 * 1024)  # limite dos RPAs: 10 arquivos x 1 MB + margem de 1 MB
    r = cliente.post(
        "/api/rpas",
        headers=h,
        data={"competencia": "2026-10"},
        files=[("arquivos", ("a.doc", enorme, "application/msword"))],
    )
    assert r.status_code == 413


def test_a8_emulador_com_projeto_real_nao_sobe(monkeypatch):
    prov = ProvedorFalso({}, set())
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    with pytest.raises(ValueError, match="emulador"):
        criar_aplicacao(CFG.model_copy(update={"gcp_project": "meu-projeto-real"}), RepositorioMemoria(), prov)
    with pytest.raises(ValueError, match="emulador"):
        criar_aplicacao(CFG, RepositorioMemoria(), prov)  # sem projeto também é recusado
    criar_aplicacao(CFG.model_copy(update={"gcp_project": "demo-rpa"}), RepositorioMemoria(), prov)  # sobe


def test_a8_sem_emulador_qualquer_projeto_sobe(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    criar_aplicacao(
        CFG.model_copy(update={"gcp_project": "meu-projeto-real"}), RepositorioMemoria(), ProvedorFalso({}, set())
    )
