import os
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest

from app.configuracao import Configuracao
from app.leitor_planilha import ErroPlanilha, ler_planilha
from tests.fixtures.planilhas import LINHAS_PADRAO, gerar_xlsx, gerar_xlsx_com_formula_sem_cache, linha

CFG = Configuracao(_env_file=None)


def _salvar(wb) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_le_aba_unica_com_metadados_de_e1_e2_a2():
    [aba] = ler_planilha(gerar_xlsx(), CFG)
    assert (aba.aba, aba.codigo_empresa, aba.competencia) == ("Planilha1", "671", "2026-10")
    assert aba.cnpj == "14.429.795/0015-68"
    assert len(aba.linhas) == len(LINHAS_PADRAO)


def test_linha_de_total_e_guardada_como_sem_recibo():
    [aba] = ler_planilha(gerar_xlsx(), CFG)
    [total] = aba.linhas_sem_recibo
    assert total.numero_linha == 6 + len(LINHAS_PADRAO)
    assert list(total.conteudo) == ["VERBA 234"]


def test_conteudo_completo_da_linha_sem_aritmetica_de_float():
    [aba] = ler_planilha(gerar_xlsx(), CFG)
    ln = next(x for x in aba.linhas if x.numero_rpa == "13809297")
    assert ln.numero_linha == 9
    assert ln.conteudo["SEST/SENAT"] == "103.3865"
    assert ln.conteudo["Nome"] == "FULANO GAMA DE SOUZA"
    assert "C.P.F." not in ln.conteudo  # célula vazia não entra


def test_arredonda_half_up_e_vazio_vale_zero():
    [aba] = ler_planilha(gerar_xlsx(), CFG)
    por_rpa = {ln.numero_rpa: ln for ln in aba.linhas}
    assert por_rpa["13809297"].sest_senat == 10339
    assert por_rpa["14070887"].sest_senat == 1723
    assert por_rpa["13915419"].inss == 14652
    assert por_rpa["13915419"].valor_bruto == 665992
    assert por_rpa["14037076"].irrf == 0
    assert por_rpa["13915419"].data_nascimento is None


def test_formula_sem_valor_calculado_e_erro_e_nao_zero():
    with pytest.raises(ErroPlanilha, match=r"linha 6 \(RPA 13915419\): fórmula sem valor calculado"):
        ler_planilha(gerar_xlsx_com_formula_sem_cache(), CFG)


def test_colunas_parametrizaveis():
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx()))
    wb["Planilha1"]["L5"] = "INSS AUTONOMO"
    cfg = CFG.model_copy(update={"sheet_colunas": CFG.sheet_colunas | {"inss": "INSS AUTONOMO"}})
    assert ler_planilha(_salvar(wb), cfg)[0].linhas[0].inss == 14652
    with pytest.raises(ErroPlanilha, match="colunas obrigatórias ausentes: inss"):
        ler_planilha(_salvar(wb), CFG)


def test_celulas_de_identificacao_parametrizaveis():
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx()))
    wb["Planilha1"]["K3"] = 999
    cfg = CFG.model_copy(update={"sheet_codigo_empresa_cell": "K3"})
    assert ler_planilha(_salvar(wb), cfg)[0].codigo_empresa == "999"


def test_multiplas_abas_uma_por_empresa():
    xlsx = gerar_xlsx(
        {
            "Nova Lima": ("671", LINHAS_PADRAO[:2]),
            "Outra": ("672", [linha(1, "FULANO X", "15000001", 1000.0, 5.0, 22.0, 0)]),
        }
    )
    abas = ler_planilha(xlsx, CFG)
    assert [(a.aba, a.codigo_empresa, len(a.linhas)) for a in abas] == [("Nova Lima", "671", 2), ("Outra", "672", 1)]


def test_aba_sem_cabecalho_e_ignorada():
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx()))
    wb.create_sheet("Notas")["A1"] = "rascunho"
    assert [a.aba for a in ler_planilha(_salvar(wb), CFG)] == ["Planilha1"]


def test_data_nascimento_quando_preenchida():
    li = linha(1, "X", "15000001", 1000.0, 5.0, 22.0, 0, nasc=datetime(1985, 4, 5))
    assert ler_planilha(gerar_xlsx({"P": ("671", [li])}), CFG)[0].linhas[0].data_nascimento == date(1985, 4, 5)


def test_erro_rpa_duplicado():
    with pytest.raises(ErroPlanilha, match="13915419"):
        ler_planilha(gerar_xlsx({"P": ("671", [LINHAS_PADRAO[0], LINHAS_PADRAO[0]])}), CFG)


def test_erro_codigo_empresa_vazio_ou_repetido():
    with pytest.raises(ErroPlanilha, match="código de empresa repetido"):
        ler_planilha(gerar_xlsx({"A": ("671", LINHAS_PADRAO[:1]), "B": ("671", LINHAS_PADRAO[1:2])}), CFG)
    wb = openpyxl.load_workbook(BytesIO(gerar_xlsx()))
    wb["Planilha1"]["E1"] = None
    with pytest.raises(ErroPlanilha, match="código da empresa vazio em E1"):
        ler_planilha(_salvar(wb), CFG)


def test_erro_arquivo_invalido_ou_sem_aba_valida():
    with pytest.raises(ErroPlanilha, match="não é uma planilha"):
        ler_planilha(b"isto nao e xlsx", CFG)
    with pytest.raises(ErroPlanilha, match="nenhuma aba"):
        ler_planilha(_salvar(openpyxl.Workbook()), CFG)


REAL = os.environ.get("RPA_PLANILHA_REAL")


@pytest.mark.integracao
@pytest.mark.skipif(not REAL, reason="defina RPA_PLANILHA_REAL=/caminho/Nova Lima.xlsx")
def test_planilha_real_nova_lima_layout_atual():
    """A amostra de out/2026 ainda usa K3/E3; quando o layout definitivo chegar, troque as células aqui."""
    cfg = CFG.model_copy(update={"sheet_codigo_empresa_cell": "K3", "sheet_cnpj_cell": "E3"})
    [aba] = ler_planilha(Path(REAL).read_bytes(), cfg)
    assert (aba.codigo_empresa, aba.competencia, len(aba.linhas), len(aba.linhas_sem_recibo)) == (
        "671",
        "2026-10",
        25,
        1,
    )
