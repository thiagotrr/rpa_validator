"""Exige LibreOffice + Tesseract (por) + poppler. Roda no container/WSL; é pulado se faltar algo."""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.extracao.extrator_texto import ErroExtracao, texto_nativo
from app.extracao.processamento import processar_rpa
from tests.fixtures import textos_rpa as t

pytestmark = pytest.mark.integracao
precisa_lo = pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice ausente")
precisa_ocr = pytest.mark.skipif(
    not (shutil.which("tesseract") and shutil.which("pdftoppm")), reason="Tesseract/poppler ausentes"
)


def _gerar_doc(tmp_path: Path, texto: str) -> bytes:
    txt = tmp_path / "rpa.txt"
    txt.write_text(texto, encoding="utf-8")
    subprocess.run(
        [
            "soffice",
            f"-env:UserInstallation={(tmp_path / 'p').as_uri()}",
            "--headless",
            "--infilter=Text (encoded):UTF8",
            "--convert-to",
            "doc:MS Word 97",
            "--outdir",
            str(tmp_path),
            str(txt),
        ],
        check=True,
        capture_output=True,
        timeout=90,
    )
    return (tmp_path / "rpa.doc").read_bytes()


@precisa_lo
def test_texto_nativo_de_doc_word97(tmp_path):
    texto = texto_nativo(_gerar_doc(tmp_path, t.A_IRRF_BRANCO), "RPA - X - 13915419.doc")
    assert "146,52" in texto and "SEST/ SENAT" in texto


@precisa_lo
def test_extensao_nao_suportada():
    with pytest.raises(ErroExtracao):
        texto_nativo(b"x", "planilha.xlsx")


@precisa_lo
@precisa_ocr
def test_ocr_forcado_extrai_campos(tmp_path):
    r = processar_rpa(_gerar_doc(tmp_path, t.B_LINHAS), "RPA - X - 14070887.doc", "2026-10", "ocr")
    assert r.metodo_extracao == "ocr"
    assert (r.inss, r.sest_senat) == (7583, 1723)


REAIS = Path(__file__).parent / "fixtures" / "docs_reais"  # .gitignore — cópia local dos .doc reais


@precisa_lo
@pytest.mark.skipif(not REAIS.exists(), reason="sem amostras reais em tests/fixtures/docs_reais")
def test_amostras_reais_extraem_todos_os_campos():
    for arq in sorted(REAIS.glob("*.doc*")):
        r = processar_rpa(arq.read_bytes(), arq.name, "2026-10", "native")
        assert r.campos_ausentes == (), f"{arq.name}: {r.campos_ausentes}"
