"""Logs JSON em stdout (o Cloud Logging lê "severity"). Nunca logar CPF nem valores de documento."""

import json
import logging
import sys
from datetime import UTC, datetime

_PADRAO = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class FormatadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
        }
        dados.update({k: v for k, v in record.__dict__.items() if k not in _PADRAO})
        if record.exc_info:
            dados["exception"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJson())
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(nivel)
    # A chave web do Firebase vai em ?key= na URL; o httpx em INFO registraria a URL completa.
    logging.getLogger("httpx").setLevel(logging.WARNING)
