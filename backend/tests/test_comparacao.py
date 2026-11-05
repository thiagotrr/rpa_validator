from dataclasses import replace
from datetime import UTC, date, datetime

from app.comparacao import comparar, planilha_para_df, rpas_para_df
from app.configuracao import Configuracao
from app.dominio import LinhaPlanilha, RpaExtraido, TipoDivergencia
from app.extracao.leitor_rpa import interpretar_rpa
from app.leitor_planilha import ler_planilha
from tests.fixtures import textos_rpa as t
from tests.fixtures.planilhas import gerar_xlsx

AGORA = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)


def ref(numero="15000001", inss=2200, irrf=0, sest=500, nasc=None, nome="FULANO DE TAL SOUZA") -> LinhaPlanilha:
    return LinhaPlanilha(
        competencia="2026-10",
        codigo_empresa="671",
        cnpj="14.429.795/0015-68",
        aba="P",
        numero_linha=6,
        numero_rpa=numero,
        matricula="1",
        nome=nome,
        valor_bruto=100000,
        inss=inss,
        irrf=irrf,
        sest_senat=sest,
        data_nascimento=nasc,
    )


def rpa(
    numero="15000001", inss=2200, irrf=0, sest=500, emissao=date(2026, 10, 20), nasc=date(1985, 4, 5), bruto=100000
) -> RpaExtraido:
    return RpaExtraido("2026-10", numero, f"RPA - X - {numero}.doc", "nativo", emissao, nasc, bruto, inss, irrf, sest)


def run(refs, rpas, tol=0):
    return comparar(planilha_para_df(refs), rpas_para_df(rpas), "2026-10", tol, agora=AGORA)


def test_sem_divergencia():
    r = run([ref()], [rpa()])
    assert r.qtd_divergencias == 0 and r.divergencias_por_campo == {}
    assert (r.qtd_documentos, r.valor_total_documentos, r.qtd_linhas_referencia) == (1, 100000, 1)
    assert (r.gerado_em, r.tolerancia_centavos) == ("2026-11-04T15:00:00+00:00", 0)


def test_valor_diferente_com_diferenca_assinada_e_nome_ofuscado():
    [d] = run([ref(inss=8683)], [rpa(inss=8681)]).divergencias
    assert (d.campo, d.tipo, d.valor_planilha, d.valor_documento, d.diferenca_centavos) == (
        "inss",
        TipoDivergencia.VALOR_DIFERENTE,
        "R$ 86,83",
        "R$ 86,81",
        -2,
    )
    assert d.nome == "FULANO DE T** S****"


def test_tolerancia_ignora_ate_o_limite_inclusive():
    assert run([ref(inss=8683)], [rpa(inss=8681)], tol=2).qtd_divergencias == 0
    assert run([ref(inss=8684)], [rpa(inss=8681)], tol=2).qtd_divergencias == 1
    assert run([ref(sest=10339)], [rpa(sest=10338)], tol=2).tolerancia_centavos == 2


def test_imposto_vazio_e_zero_tem_o_mesmo_peso():
    # vazio já chega como 0 dos leitores (planilha e RPA); 0 x 0 não diverge
    assert run([ref(irrf=0)], [rpa(irrf=0)]).qtd_divergencias == 0


def test_campo_nao_extraido():
    r = run([ref()], [replace(rpa(), irrf=None, data_emissao=None)])
    assert [(d.campo, d.tipo) for d in r.divergencias] == [
        ("irrf", TipoDivergencia.CAMPO_NAO_EXTRAIDO),
        ("data_emissao", TipoDivergencia.CAMPO_NAO_EXTRAIDO),
    ]


def test_emissao_fora_da_competencia():
    [d] = run([ref()], [rpa(emissao=date(2026, 11, 2))]).divergencias
    assert (d.tipo, d.valor_documento) == (TipoDivergencia.DATA_FORA_COMPETENCIA, "02/11/2026")


def test_nascimento_so_compara_quando_planilha_tem():
    assert run([ref(nasc=None)], [rpa(nasc=date(2000, 1, 1))]).qtd_divergencias == 0
    [d] = run([ref(nasc=date(1985, 4, 5))], [rpa(nasc=date(1985, 5, 4))]).divergencias
    assert d.tipo == TipoDivergencia.DATA_DIFERENTE


def test_registros_sem_par():
    r = run([ref("15000001"), ref("15000002")], [rpa("15000001"), rpa("15000003")])
    assert [(d.numero_rpa, d.tipo, d.nome) for d in r.divergencias] == [
        ("15000002", TipoDivergencia.REFERENCIA_SEM_RPA, "FULANO DE T** S****"),
        ("15000003", TipoDivergencia.RPA_SEM_REFERENCIA, None),
    ]
    assert r.divergencias_por_campo == {"registro": 2}


def test_sem_rpas_carregados():
    r = run([ref()], [])
    assert r.qtd_documentos == 0 and r.valor_total_documentos == 0
    assert r.divergencias[0].tipo == TipoDivergencia.REFERENCIA_SEM_RPA


def test_ordem_deterministica():
    refs = [ref("15000002", inss=1), ref("15000001", inss=1, sest=1)]
    rpas = [rpa("15000001"), rpa("15000002")]
    r1, r2 = run(refs, rpas), run(list(reversed(refs)), list(reversed(rpas)))
    assert r1 == r2
    assert [(d.numero_rpa, d.campo) for d in r1.divergencias] == [
        ("15000001", "inss"),
        ("15000001", "sest_senat"),
        ("15000002", "inss"),
    ]


def test_golden_casos_reais_nova_lima():
    """Layout real: com tolerância 0 aparecem as 2 diferenças de centavos de out/2026; com o padrão (2), nenhuma."""
    [aba] = ler_planilha(gerar_xlsx(), Configuracao(_env_file=None))
    textos = {
        "13915419": t.A_IRRF_BRANCO,
        "14037118": t.A_INSS_COLADO,
        "14070887": t.B_LINHAS,
        "13809297": t.A_SEST_TRUNCADO,
        "14090502": t.A_INSS_DIVERGENTE,
        "14037076": t.A_ZERO_CURTO,
    }
    rpas = [
        interpretar_rpa(txt, arquivo=f"RPA - X - {n}.doc", competencia="2026-10", metodo="nativo")
        for n, txt in textos.items()
    ]
    df_ref, df_rpa = planilha_para_df(list(aba.linhas)), rpas_para_df(rpas)

    r0 = comparar(df_ref, df_rpa, "2026-10", 0, agora=AGORA)
    assert [(d.numero_rpa, d.campo, d.valor_planilha, d.valor_documento, d.nome) for d in r0.divergencias] == [
        ("13809297", "sest_senat", "R$ 103,39", "R$ 103,38", "FULANO G*** DE S****"),
        ("14090502", "inss", "R$ 86,83", "R$ 86,81", "FULANO D**** DE M***"),
    ]
    assert comparar(df_ref, df_rpa, "2026-10", Configuracao(_env_file=None).tolerancia_centavos).qtd_divergencias == 0
