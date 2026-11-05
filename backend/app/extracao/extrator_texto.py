"""Converte o binário do Word em texto. O arquivo vive só num diretório temporário e é apagado ao final."""

import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SEGUNDOS = 90
EXTENSOES_ACEITAS = (".doc", ".docx")


class ErroExtracao(RuntimeError):
    pass


def _soffice() -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise ErroExtracao("LibreOffice (soffice) não encontrado no PATH")
    return exe


def _converter(conteudo: bytes, nome_arquivo: str, filtro: str, workdir: Path) -> Path:
    sufixo = Path(nome_arquivo).suffix.lower()
    if sufixo not in EXTENSOES_ACEITAS:
        raise ErroExtracao(f"extensão não suportada: {sufixo or '(sem extensão)'}")
    entrada = workdir / f"entrada{sufixo}"
    entrada.write_bytes(conteudo)
    # Perfil isolado por chamada: permite conversões simultâneas na mesma instância do Cloud Run.
    perfil = (workdir / "perfil-lo").as_uri()
    cmd = [
        _soffice(),
        f"-env:UserInstallation={perfil}",
        "--headless",
        "--norestore",
        "--convert-to",
        filtro,
        "--outdir",
        str(workdir),
        str(entrada),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_SEGUNDOS, check=False)
    except subprocess.TimeoutExpired as e:
        raise ErroExtracao("tempo esgotado na conversão do documento") from e
    saida = workdir / f"entrada.{filtro.split(':')[0]}"
    if r.returncode != 0 or not saida.exists():
        raise ErroExtracao(f"falha na conversão ({filtro}): {r.stderr.decode(errors='ignore')[:300]}")
    return saida


def texto_nativo(conteudo: bytes, nome_arquivo: str) -> str:
    with tempfile.TemporaryDirectory(prefix="rpa-") as d:
        saida = _converter(conteudo, nome_arquivo, "txt:Text (encoded):UTF8", Path(d))
        return saida.read_text(encoding="utf-8", errors="replace")


def texto_ocr(conteudo: bytes, nome_arquivo: str) -> str:
    import pytesseract
    from pdf2image import convert_from_path

    with tempfile.TemporaryDirectory(prefix="rpa-") as d:
        pdf = _converter(conteudo, nome_arquivo, "pdf", Path(d))
        paginas = convert_from_path(str(pdf), dpi=300)
        return "\n".join(pytesseract.image_to_string(p, lang="por", config="--psm 6") for p in paginas)
