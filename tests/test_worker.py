import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _configurar_core(mock_core, n_arquivos):
    """Dá ao mock do núcleo o contrato v2.9 que o Worker consome."""
    mock_core.MAX_MB_PARTE = 100
    mock_core.P_LIMPEZA = 1.0
    mock_core.P_OCR = 30.0
    mock_core.P_NUMERA = 0.1
    mock_core.P_DIVIDE = 0.1
    mock_core.P_EXPORT = 1.0
    mock_core.planejar.side_effect = lambda arqs, com_ocr=True: [
        {"paginas": 1, "paginas_ocr": 0, "unidades": 1.0} for _ in arqs
    ]
    mock_core.dividir_pdf.side_effect = lambda p, m, **kw: [(p, 1)]


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
        _configurar_core(mock_core, 2)

        def limpa_e_cancela(src, dst, sem_cab, **kw):
            limpos.mkdir(parents=True, exist_ok=True)
            dst.touch()
            w.requisitar_cancelamento()
            return 0

        mock_core.limpa_pdf.side_effect = limpa_e_cancela

        from gui import Worker
        w = Worker([pdf1, pdf2], opcoes)
        w.terminou.connect(lambda g, c: resultados.update({"gerados": g, "cancelado": c}))
        w.run()

    assert resultados.get("cancelado") is True
    assert mock_core.limpa_pdf.call_count == 1


def test_limpa_pdf_recebe_progresso_e_cancelar(qapp, tmp_path):
    """Contrato v2.9: o Worker repassa progresso= e cancelar= ao núcleo."""
    pdf = tmp_path / "a.pdf"
    pdf.touch()
    limpos = tmp_path / "LIMPOS"

    opcoes = {
        "ocr": False, "paginar": False, "dividir": False,
        "max_mb": 0, "md": False, "sem_cabecalho": True,
    }

    with patch("gui.core") as mock_core:
        _configurar_core(mock_core, 1)

        def fake_limpa(src, dst, sem_cab, **kw):
            limpos.mkdir(parents=True, exist_ok=True)
            dst.touch()
            return 0

        mock_core.limpa_pdf.side_effect = fake_limpa

        from gui import Worker
        w = Worker([pdf], opcoes)
        w.run()

    kwargs = mock_core.limpa_pdf.call_args.kwargs
    assert callable(kwargs.get("progresso"))
    assert kwargs.get("cancelar") is w._cancelar


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
        _configurar_core(mock_core, 1)

        def fake_limpa(src, dst, sem_cab, **kw):
            limpos.mkdir(parents=True, exist_ok=True)
            dst.touch()
            return 0

        mock_core.limpa_pdf.side_effect = fake_limpa

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
