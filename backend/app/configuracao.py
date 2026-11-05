from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# campo interno -> rótulo da coluna na planilha. Sobrescreva com SHEET_COLUNAS='{"inss": "INSS EMPREGADO", ...}'.
COLUNAS_PADRAO = {
    "matricula": "Matr.",
    "nome": "Nome",
    "data_nascimento": "DATA NASC.",
    "numero_rpa": "Nº RECIBO",  # âncora: a linha com este rótulo é o cabeçalho
    "valor_bruto": "VERBA 234",
    "sest_senat": "SEST/SENAT",
    "inss": "INSS EMPREGADO",
    "irrf": "IR EMPREGADO",
}


class Configuracao(BaseSettings):
    """Lida de variáveis de ambiente (nome em maiúsculas: FIREBASE_WEB_API_KEY, TOLERANCIA_CENTAVOS, ...)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Autenticação (Firebase Auth). A chave web fica só no backend (Secret Manager), nunca no front-end.
    firebase_web_api_key: str = ""
    claim_acesso: str = "rpa_autorizado"  # custom claim gravado pela carga manual de acessos
    login_max_attempts: int = 5
    login_window_minutes: int = 15

    repository_backend: str = "firestore"  # firestore | memory
    gcp_project: str | None = None
    firestore_database: str = "(default)"

    extraction_mode: str = "auto"  # auto | native | ocr
    tolerancia_centavos: int = 2  # diferenças de até 2 centavos são ignoradas
    max_upload_mb: int = 10
    max_arquivos_por_lote: int = 50
    static_dir: str = "static"

    # Layout da planilha — PROVISÓRIO até a confirmação do layout definitivo.
    sheet_competencia_cell: str = "A2"
    sheet_codigo_empresa_cell: str = "E1"
    sheet_cnpj_cell: str = "E2"
    sheet_colunas: dict[str, str] = Field(default_factory=lambda: dict(COLUNAS_PADRAO))

    @field_validator("sheet_colunas")
    @classmethod
    def _mesclar_colunas(cls, v: dict[str, str]) -> dict[str, str]:
        """SHEET_COLUNAS parcial sobrescreve só os rótulos informados; o resto fica com o padrão."""
        desconhecidos = set(v) - set(COLUNAS_PADRAO)
        if desconhecidos:
            raise ValueError(f"campos desconhecidos em SHEET_COLUNAS: {', '.join(sorted(desconhecidos))}")
        return COLUNAS_PADRAO | v


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
