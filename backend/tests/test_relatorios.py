from app.dominio import Divergencia, Relatorio, TipoDivergencia
from app.relatorios import _html_do_pdf, gerar_markdown, gerar_pdf, relatorio_para_dicionario

R = Relatorio(
    competencia="2026-10",
    gerado_em="2026-11-04T15:00:00+00:00",
    tolerancia_centavos=2,
    qtd_documentos=25,
    valor_total_documentos=16575424,
    qtd_linhas_referencia=25,
    qtd_divergencias=2,
    divergencias_por_campo={"inss": 1, "sest_senat": 1},
    divergencias=(
        Divergencia(
            "13809297", "671", "FULANO <C>", "sest_senat", TipoDivergencia.VALOR_DIFERENTE, "R$ 103,39", "R$ 103,38", -1
        ),
        Divergencia(
            "14090502", "671", "FULANO | D", "inss", TipoDivergencia.VALOR_DIFERENTE, "R$ 86,83", "R$ 86,81", -2
        ),
    ),
)
VAZIO = Relatorio("2026-10", "2026-11-04T15:00:00+00:00", 2, 0, 0, 0, 0, {}, ())


def test_dict_serializavel_para_json():
    import json

    d = relatorio_para_dicionario(R)
    assert d["divergencias"][0]["tipo"] == "VALOR_DIFERENTE"
    json.dumps(d)


def test_markdown_cards_por_campo_e_detalhes():
    md = gerar_markdown(R)
    assert "| Valor total dos documentos | R$ 165.754,24 |" in md
    assert "| SEST/SENAT | 1 |" in md
    assert "| Tolerância (diferenças ignoradas até) | R$ 0,02 |" in md
    assert "| 14090502 | 671 | FULANO \\| D | INSS | Valor diferente | R$ 86,83 | R$ 86,81 |" in md


def test_markdown_sem_divergencias():
    assert "Nenhuma divergência encontrada." in gerar_markdown(VAZIO)


def test_modelo_do_pdf_escapa_conteudo():
    html = _html_do_pdf(R)  # HTML interno: só alimenta o PDF
    assert "FULANO &lt;C&gt;" in html and "FULANO <C>" not in html


def test_pdf_valido():
    pdf = gerar_pdf(R)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
