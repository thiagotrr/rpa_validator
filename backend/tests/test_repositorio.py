import os
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.dominio import AbaPlanilha, LinhaPlanilha, LinhaSemRecibo, RpaExtraido
from app.repositorio import (
    COL_PLANILHA,
    COL_PLANILHA_CONTEUDO,
    RepositorioFirestore,
    RepositorioMemoria,
    TentativasLogin,
    documento_para_linha,
    documento_para_rpa,
    id_documento_linha,
    id_documento_rpa,
    linha_para_documento,
    rpa_para_documento,
)

AGORA = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
TOTAL = LinhaSemRecibo(numero_linha=31, conteudo={"VERBA 234": "165754.24"})


def linha(numero, numero_linha=6, competencia="2026-10", empresa="671"):
    return LinhaPlanilha(
        competencia,
        empresa,
        "14.429.795/0015-68",
        "P",
        numero_linha,
        numero,
        "1",
        "FULANO",
        100000,
        2200,
        0,
        500,
        date(1985, 4, 5),
        {"Nome": "FULANO", "INSS EMPREGADO": "22.0"},
    )


def rpa(numero, competencia="2026-10"):
    return RpaExtraido(
        competencia,
        numero,
        f"RPA {numero}.doc",
        "nativo",
        date(2026, 10, 20),
        None,
        100000,
        2200,
        0,
        500,
        ("data_nascimento",),
    )


def aba(linhas, competencia="2026-10", empresa="671", sem_recibo=()):
    return AbaPlanilha("P", empresa, "14.429.795/0015-68", competencia, tuple(linhas), tuple(sem_recibo))


def carregar(repo, competencia, abas, arquivo="a.xlsx"):
    repo.substituir_planilha(competencia, abas, arquivo=arquivo, usuario="u", agora=AGORA)


def numeros(repo, competencia):
    return [ln.numero_rpa for ln in repo.listar_planilha(competencia)]


def test_serializacao_ida_e_volta():
    ln, r = linha("15000001"), rpa("15000001")
    doc = linha_para_documento(ln)
    assert (doc["data_nascimento"], doc["tipo_linha"], doc["conteudo"]["Nome"]) == ("1985-04-05", "rpa", "FULANO")
    assert documento_para_linha(doc) == ln
    assert rpa_para_documento(r)["campos_ausentes"] == ["data_nascimento"]
    assert documento_para_rpa(rpa_para_documento(r) | {"carregado_por": "x"}) == r


def test_ids_dos_documentos():
    assert id_documento_rpa("2026-10", "14090502") == "2026-10_14090502"
    assert id_documento_linha("2026-10", "671", 9) == "2026-10_671_00009"


def contrato(repo):
    carregar(
        repo,
        "2026-10",
        [
            aba([linha("15000001", 6), linha("15000002", 7)], sem_recibo=[TOTAL]),
            aba([linha("16000001", 6, empresa="672")], empresa="672"),
        ],
    )
    carregar(repo, "2026-09", [aba([linha("14000001", 6, competencia="2026-09")], competencia="2026-09")])
    assert numeros(repo, "2026-10") == ["15000001", "15000002", "16000001"]
    assert repo.listar_planilha("2026-08") == []

    # RPAs já carregados convivem com a recarga da planilha
    repo.salvar_rpa(rpa("15000003"), usuario="u", agora=AGORA)
    repo.salvar_rpa(replace(rpa("15000003"), inss=1), usuario="u", agora=AGORA)  # recarga do mesmo RPA sobrescreve
    repo.salvar_rpa(rpa("15000003", competencia="2026-11"), usuario="u", agora=AGORA)

    # planilha nova da mesma competência SUBSTITUI tudo: some a empresa 672 e as linhas antigas da 671
    carregar(repo, "2026-10", [aba([linha("15000003", 6)])], arquivo="b.xlsx")
    assert numeros(repo, "2026-10") == ["15000003"]
    assert numeros(repo, "2026-09") == ["14000001"]  # outra competência intacta

    [r] = repo.listar_rpas("2026-10")
    assert r.inss == 1  # o RPA carregado antes continua lá
    assert repo.numeros_rpas("2026-10") == {"15000003"}
    assert repo.numeros_rpas("2026-11") == {"15000003"}
    assert repo.numeros_rpas("2026-08") == set()

    t = TentativasLogin(2, AGORA, None)
    repo.salvar_tentativas("k", t)
    assert repo.obter_tentativas("k") == t
    repo.limpar_tentativas("k")
    assert repo.obter_tentativas("k") is None


def test_contrato_memoria():
    contrato(RepositorioMemoria())


def test_memoria_guarda_cada_linha_inclusive_sem_recibo():
    repo = RepositorioMemoria()
    carregar(repo, "2026-10", [aba([linha("15000001", 6)], sem_recibo=[TOTAL])])
    assert set(repo.conteudo) == {"2026-10_671_00006", "2026-10_671_00031"}
    assert repo.conteudo["2026-10_671_00031"]["tipo_linha"] == "sem_recibo"
    assert repo.planilha["2026-10_671"]["qtd_linhas_sem_recibo"] == 1


def test_recarga_apaga_linhas_e_metadados_que_sobraram():
    repo = RepositorioMemoria()
    carregar(
        repo,
        "2026-10",
        [aba([linha("15000001", 6)], sem_recibo=[TOTAL]), aba([linha("16000001", 6, empresa="672")], empresa="672")],
    )
    carregar(repo, "2026-10", [aba([linha("15000001", 6)])])
    assert set(repo.conteudo) == {"2026-10_671_00006"}  # sumiram a linha de total e a empresa 672
    assert set(repo.planilha) == {"2026-10_671"}


def test_substituir_recusa_lote_vazio_ou_de_outra_competencia_sem_apagar_nada():
    repo = RepositorioMemoria()
    carregar(repo, "2026-10", [aba([linha("15000001", 6)])])
    with pytest.raises(ValueError, match="sem abas"):
        carregar(repo, "2026-10", [])
    with pytest.raises(ValueError, match="competência diferente de 2026-10: 2026-09"):
        carregar(repo, "2026-10", [aba([linha("1", 6, competencia="2026-09")], competencia="2026-09")])
    assert numeros(repo, "2026-10") == ["15000001"]


def test_nomes_das_collections():
    assert (COL_PLANILHA, COL_PLANILHA_CONTEUDO) == ("planilha_conferencia", "planilha_conferencia_conteudo")


@pytest.mark.integracao
@pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="emulador do Firestore não configurado")
def test_contrato_firestore_emulador():
    contrato(RepositorioFirestore(project=f"teste-{uuid.uuid4().hex[:8]}"))
