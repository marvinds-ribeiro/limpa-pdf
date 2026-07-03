"""Resolução do Tesseract EMBUTIDO no app congelado (PyInstaller).

Reproduz o erro do empacotamento (prints/log de erros.txt):
  - Tentativa 1: "OCR indisponível" — _preparar_ocr só olhava o PATH e as
    pastas de instalação do sistema; o tesseract.exe embutido no bundle
    (sys._MEIPASS/tesseract/) era ignorado em máquinas sem Tesseract
    instalado. Na máquina de dev, pior: o exe do SISTEMA sobrescrevia o
    tesseract_cmd apontado para o bundle.
  - Tentativa 2: 'Error opening data file "..."/por.traineddata' — o
    TESSDATA_PREFIX errado (pasta tesseract/ em vez de tesseract/tessdata/)
    caía no --tessdata-dir com aspas literais (shlex não-posix do
    pytesseract no Windows) e o Tesseract não carregava o idioma.

O contrato testado aqui: num app congelado, _preparar_ocr usa o exe E o
tessdata do bundle, via TESSDATA_PREFIX, sem depender de nada do sistema e
sem baixar nada (operação 100% offline).
"""
import os
import sys

import pytest

import limpa_pdf_mpsc as core


def _bundle_falso(tmp_path):
    """Monta a MESMA árvore que o limpa_pdf.spec produz em _internal/."""
    tess = tmp_path / "tesseract"
    (tess / "tessdata").mkdir(parents=True)
    (tess / "tesseract.exe").write_bytes(b"MZ dummy")
    (tess / "tessdata" / "por.traineddata").write_bytes(b"dummy")
    return tess


def test_preparar_ocr_usa_tesseract_do_bundle_congelado(tmp_path, monkeypatch):
    import pytesseract
    tess = _bundle_falso(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    # registra o valor atual p/ restauração automática após o teste
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd",
                        pytesseract.pytesseract.tesseract_cmd)

    lang, cfg = core._preparar_ocr()

    # exe: o do bundle, NÃO o do sistema (mesmo que haja um instalado)
    assert pytesseract.pytesseract.tesseract_cmd == str(tess / "tesseract.exe")
    # idioma: o por.traineddata do bundle, via TESSDATA_PREFIX (sem aspas)
    assert lang == "por"
    assert os.environ.get("TESSDATA_PREFIX") == str(tess / "tessdata")
    assert cfg == ""


def test_gui_nao_seta_tessdata_prefix_errado():
    """O gui.py setava TESSDATA_PREFIX = <MEIPASS>/tesseract (pasta ERRADA:
    o Tesseract 5 exige a pasta tessdata em si). A resolução do bundle agora
    é responsabilidade única do core (_preparar_ocr); o gui não deve mais
    manipular TESSDATA_PREFIX nem tesseract_cmd."""
    import inspect
    import gui
    fonte = inspect.getsource(gui)
    assert "TESSDATA_PREFIX" not in fonte
    assert "tesseract_cmd" not in fonte
