from datetime import UTC, date, datetime
from io import BytesIO

import openpyxl
import pytest

from app.cargas import (
    CompetenciaDivergente,
    carregar_planilha,
    decidir_arquivo,
    situacao_planilha,
    verificar_envio_rpas,
)
from app.configuracao import Configuracao
from app.dominio import RpaExtraido
from app.leitor_planilha import ErroPlanilha
from app.repositorio import RepositorioMemoria
from tests.fixtures.planilhas import LINHAS_PADRAO, gerar_xlsx, linha

CFG = Configuracao(_env_file=None)
AGORA = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)


def carregar(repo, xlsx, informada="2026-10", prevalece=None, arquivo="a.xlsx"):
    return carregar_planilha(
        xlsx,
        cfg=CFG,
        repo=repo,
        competencia_informada=informada,
        prevalece=prevalece,
        arquivo=arquivo,
        usuario="u",
        agora=AGORA,
    )


def rpa(numero, competencia="2026-10"):
    return RpaExtraido(competencia, numero, f"RPA {numero}.doc", "nativo", date(2026, 10, 20), None, 1, 0, 0, 0, ())


def nomes(*numeros):
    return [f"RPA - FULANO - {n}.doc" for n in numeros]


def test_carregar_planilha_grava_e_resume():
    repo = RepositorioMemoria()
    r = carregar(repo, gerar_xlsx())
    assert (r.competencia, r.competencia_arquivo, r.qtd_linhas_substituidas) == ("2026-10", "2026-10", 0)
    assert r.abas == [
        {
            "aba": "Planilha1",
            "codigo_empresa": "671",
            "cnpj": "14.429.795/0015-68",
            "competencia": "2026-10",
            "qtd_linhas": 6,
            "qtd_linhas_sem_recibo": 1,
        }
    ]
    assert r.erros_abas == []
    assert len(repo.listar_planilha("2026-10")) == 6


def test_nova_planilha_da_mesma_competencia_substitui_tudo():
    repo = RepositorioMemoria()
    carregar(repo, gerar_xlsx({"A": ("671", LINHAS_PADRAO[:3]), "B": ("672", LINHAS_PADRAO[3:])}))
    novo = gerar_xlsx({"C": ("673", [linha(1, "FULANO X", "15000001", 1000.0, 5.0, 22.0, 0)])})
    r = carregar(repo, novo, arquivo="b.xlsx")
    assert r.qtd_linhas_substituidas == 6
    assert [(ln.codigo_empresa, ln.numero_rpa) for ln in repo.listar_planilha("2026-10")] == [("673", "15000001")]


def test_divergencia_de_competencia_nao_grava_nem_apaga_nada():
    repo = RepositorioMemoria()
    carregar(repo, gerar_xlsx())
    outra = gerar_xlsx({"C": ("673", [linha(1, "FULANO X", "15000001", 1000.0, 5.0, 22.0, 0)])})
    with pytest.raises(CompetenciaDivergente) as e:
        carregar(repo, outra, informada="2026-11")
    assert (e.value.competencia_arquivo, e.value.competencia_informada) == ("2026-10", "2026-11")
    assert len(repo.listar_planilha("2026-10")) == 6 and repo.listar_planilha("2026-11") == []


def test_prevalece_tela_grava_na_competencia_escolhida():
    repo = RepositorioMemoria()
    r = carregar(repo, gerar_xlsx(), informada="2026-11", prevalece="tela")
    assert (r.competencia, r.competencia_arquivo) == ("2026-11", "2026-10")
    assert repo.listar_planilha("2026-10") == []
    assert {ln.competencia for ln in repo.listar_planilha("2026-11")} == {"2026-11"}
    assert all(m["competencia"] == "2026-11" for m in repo.planilha.values())


def test_prevalece_arquivo_grava_na_competencia_da_planilha():
    repo = RepositorioMemoria()
    r = carregar(repo, gerar_xlsx(), informada="2026-11", prevalece="arquivo")
    assert r.competencia == "2026-10" and len(repo.listar_planilha("2026-10")) == 6


def test_aba_com_erro_e_listada_e_as_outras_sao_gravadas():
    wb = openpyxl.load_workbook(
        BytesIO(gerar_xlsx({"Boa": ("671", LINHAS_PADRAO[:2]), "Ruim": ("672", LINHAS_PADRAO[2:3])}))
    )
    wb["Ruim"]["E1"] = None
    buf = BytesIO()
    wb.save(buf)
    repo = RepositorioMemoria()
    r = carregar(repo, buf.getvalue())
    assert [a["aba"] for a in r.abas] == ["Boa"] and [e["aba"] for e in r.erros_abas] == ["Ruim"]
    assert {ln.codigo_empresa for ln in repo.listar_planilha("2026-10")} == {"671"}


def test_arquivo_invalido_preserva_a_planilha_anterior():
    repo = RepositorioMemoria()
    carregar(repo, gerar_xlsx())
    with pytest.raises(ErroPlanilha):
        carregar(repo, b"nao e xlsx")
    assert len(repo.listar_planilha("2026-10")) == 6


def test_rpas_ja_carregados_sobrevivem_a_nova_planilha():
    repo = RepositorioMemoria()
    carregar(repo, gerar_xlsx())
    repo.salvar_rpa(rpa("13915419"), usuario="u", agora=AGORA)
    carregar(repo, gerar_xlsx(), arquivo="b.xlsx")
    assert repo.numeros_rpas("2026-10") == {"13915419"}


def test_situacao_planilha():
    repo = RepositorioMemoria()
    assert situacao_planilha(repo, "2026-10") == {
        "competencia": "2026-10",
        "carregada": False,
        "qtd_linhas": 0,
        "empresas": [],
    }
    carregar(repo, gerar_xlsx())
    s = situacao_planilha(repo, "2026-10")
    assert (s["carregada"], s["qtd_linhas"], s["empresas"]) == (True, 6, ["671"])


def planilha_com_6(repo):
    carregar(repo, gerar_xlsx())


def test_verificacao_sem_planilha():
    v = verificar_envio_rpas(RepositorioMemoria(), "2026-10", nomes("13915419"))
    assert (v.planilha_carregada, v.confere, v.qtd_linhas_planilha, v.qtd_novos) == (False, False, 0, 1)


def test_verificacao_quantitativo_confere():
    repo = RepositorioMemoria()
    planilha_com_6(repo)
    v = verificar_envio_rpas(
        repo, "2026-10", nomes("13915419", "14037118", "14070887", "13809297", "14090502", "14037076")
    )
    assert (v.confere, v.diferenca, v.qtd_novos, v.qtd_total_apos_envio) == (True, 0, 6, 6)


def test_verificacao_faltam_rpas_considerando_os_ja_carregados():
    repo = RepositorioMemoria()
    planilha_com_6(repo)
    repo.salvar_rpa(rpa("13915419"), usuario="u", agora=AGORA)
    v = verificar_envio_rpas(repo, "2026-10", nomes("14037118", "14070887", "13915419"))
    assert (v.qtd_ja_carregados, v.qtd_ja_existentes_no_envio, v.qtd_novos) == (1, 1, 2)
    assert (v.qtd_total_apos_envio, v.diferenca, v.confere) == (3, -3, False)


def test_verificacao_sobram_repetidos_e_sem_numero():
    repo = RepositorioMemoria()
    planilha_com_6(repo)
    envio = nomes(*(f"1500000{i}" for i in (1, 2, 3, 4, 5, 6, 7, 7))) + ["RPA sem numero.doc"]
    v = verificar_envio_rpas(repo, "2026-10", envio)
    assert (v.qtd_arquivos, v.qtd_sem_numero, v.qtd_repetidos_no_envio) == (9, 1, 1)
    assert (v.qtd_total_apos_envio, v.diferenca, v.confere) == (7, 1, False)


def test_decidir_arquivo():
    vistos: set[str] = set()
    ja = {"2"}
    assert decidir_arquivo("1", vistos=vistos, ja_carregados=ja, substituir=False) == "processar"
    assert decidir_arquivo("1", vistos=vistos, ja_carregados=ja, substituir=False) == "repetido_no_envio"
    assert decidir_arquivo("2", vistos=vistos, ja_carregados=ja, substituir=False) == "ja_carregado"
    assert decidir_arquivo("2", vistos={"x"}, ja_carregados=ja, substituir=True) == "processar"
