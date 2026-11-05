import pytest
from pydantic import ValidationError

from app.configuracao import COLUNAS_PADRAO, Configuracao


def test_padroes_das_decisoes():
    cfg = Configuracao(_env_file=None)
    assert (cfg.tolerancia_centavos, cfg.extraction_mode, cfg.login_max_attempts) == (2, "auto", 5)
    assert (cfg.sheet_competencia_cell, cfg.sheet_codigo_empresa_cell, cfg.sheet_cnpj_cell) == ("A2", "E1", "E2")


def test_sheet_colunas_parcial_mescla_com_o_padrao(monkeypatch):
    monkeypatch.setenv("SHEET_COLUNAS", '{"inss": "INSS AUTONOMO"}')
    cfg = Configuracao(_env_file=None)
    assert cfg.sheet_colunas["inss"] == "INSS AUTONOMO"
    assert cfg.sheet_colunas["irrf"] == COLUNAS_PADRAO["irrf"]


def test_sheet_colunas_rejeita_campo_desconhecido(monkeypatch):
    monkeypatch.setenv("SHEET_COLUNAS", '{"cpf": "C.P.F."}')
    with pytest.raises(ValidationError, match="cpf"):
        Configuracao(_env_file=None)
