import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_cancela_apos_limpa_pdf_do_primeiro_arquivo(qapp, tmp_path):
    """Worker para antes do segundo arquivo quando cancelado após limpa_pdf do primeiro."""
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    pdf1.touch()
    pdf2.touch()
    limpos = tmp_path / "LIMPOS"

    opcoes = {
        "ocr": False, "paginar": False, "dividir": False,
        "max_mb": 0, "md": False, "sem_cabecalho": True,
    }
    resultados = {}

    with patch("gui.core") as mock_core:
        mock_core.MAX_MB_PARTE = 100

        def limpa_e_cancela(src, dst, sem_cab):
            limpos.mkdir(parents=True, exist_ok=True)
            dst.touch()
            w.requisitar_cancelamento()
            return 0

        mock_core.limpa_pdf.side_effect = limpa_e_cancela
        mock_core.dividir_pdf.side_effect = lambda p, m: [(p, 1)]

        from gui import Worker
        w = Worker([pdf1, pdf2], opcoes)
        w.terminou.connect(lambda g, c: resultados.update({"gerados": g, "cancelado": c}))
        w.run()

    assert resultados.get("cancelado") is True
    assert mock_core.limpa_pdf.call_count == 1


def test_emite_cancelado_false_quando_completo(qapp, tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.touch()
    limpos = tmp_path / "LIMPOS"

    opcoes = {
        "ocr": False, "paginar": False, "dividir": False,
        "max_mb": 0, "md": False, "sem_cabecalho": True,
    }
    resultados = {}

    with patch("gui.core") as mock_core:
        mock_core.MAX_MB_PARTE = 100

        def fake_limpa(src, dst, sem_cab):
            limpos.mkdir(parents=True, exist_ok=True)
            dst.touch()
            return 0

        mock_core.limpa_pdf.side_effect = fake_limpa
        mock_core.dividir_pdf.side_effect = lambda p, m: [(p, 1)]

        from gui import Worker
        w = Worker([pdf], opcoes)
        w.terminou.connect(lambda g, c: resultados.update({"gerados": g, "cancelado": c}))
        w.run()

    assert resultados.get("cancelado") is False


def test_erro_quando_sem_pdfs(qapp, tmp_path):
    opcoes = {
        "ocr": False, "paginar": False, "dividir": False,
        "max_mb": 0, "md": False, "sem_cabecalho": True,
    }
    erros = []

    with patch("gui.core"):
        from gui import Worker
        w = Worker([tmp_path], opcoes)   # diretório vazio
        w.erro.connect(erros.append)
        w.run()

    assert len(erros) == 1
    assert "Nenhum PDF" in erros[0]
