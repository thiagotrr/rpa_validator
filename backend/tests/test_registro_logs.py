import json
import logging

from app.registro_logs import FormatadorJson, configurar_logs


def test_formatador_gera_json_com_severity_e_campos_extras():
    registro = logging.LogRecord("rpa", logging.WARNING, __file__, 1, "evento", (), None)
    registro.competencia = "2026-10"
    dados = json.loads(FormatadorJson().format(registro))
    assert (dados["severity"], dados["message"], dados["competencia"]) == ("WARNING", "evento", "2026-10")


def test_a7_logger_do_httpx_fica_em_warning_para_nao_registrar_a_chave_na_url():
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    configurar_logs("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
