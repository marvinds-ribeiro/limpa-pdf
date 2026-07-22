# -*- coding: utf-8 -*-
"""Testes do classificador de tipo de página (v2.10, e-proc/TJSC).

Valores esperados vêm do diagnóstico medido em RELATORIO_EPROC.md:
- ex1.pdf pág. 1 (0-based 0): página de separação — texto nativo, sem scan;
- pág. 2 (1): scan em Form XObject + só moldura (264 chars) → híbrida com
  camada DEFICIENTE (densidade 21,8 < FRAC_TEXTO_MIN_HIBRIDO);
- pág. 23 (22): scan quase em branco (tinta 0.008, densidade 63,8) → híbrida
  NÃO deficiente (nada a recuperar; reusa);
- pág. 31 (30): "Assinaturas do documento" — texto nativo.

E a regra inegociável do atl.md §6: nos arquivos do SIG a verificação de
densidade NÃO pode alterar decisões (nativa jamais vira deficiente).
"""
import shutil
import sys
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import limpa_pdf_mpsc as nucleo  # noqa: E402

EX1 = RAIZ / "exemplos" / "ex1.pdf"
SIG1 = RAIZ / "exemplos" / "exemplo 1.pdf"


def _classificar(caminho, i):
    pdf = pikepdf.open(caminho)
    doc = pdfium.PdfDocument(str(caminho))
    try:
        tp = doc[i].get_textpage()
        texto = (tp.get_text_range() or "").strip()
        tp.close()
        return nucleo.classificar_pagina(pdf.pages[i], doc[i], texto)
    finally:
        pdf.close()
        doc.close()


@pytest.mark.skipif(not EX1.exists(), reason="exemplos/ex1.pdf ausente")
class TestEx1:
    def test_pagina_separacao_e_nativa(self):
        tipo, deficiente, bbox = _classificar(EX1, 0)
        assert tipo is nucleo.TipoPagina.NATIVA_DIGITAL
        assert not deficiente and bbox is None

    def test_scan_com_moldura_e_hibrida_deficiente(self):
        tipo, deficiente, bbox = _classificar(EX1, 1)   # pág. 2: dens 21,8
        assert tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR
        assert deficiente
        assert bbox is not None
        # o bbox do scan cobre >= 80% da página (595x842)
        assert (bbox[2] - bbox[0]) >= 0.8 * 595
        assert (bbox[3] - bbox[1]) >= 0.8 * 842

    def test_scan_quase_em_branco_nao_e_deficiente(self):
        tipo, deficiente, _ = _classificar(EX1, 22)     # pág. 23: dens 63,8
        assert tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR
        assert not deficiente

    def test_pagina_assinaturas_e_nativa(self):
        tipo, _, _ = _classificar(EX1, 30)              # pág. 31
        assert tipo is nucleo.TipoPagina.NATIVA_DIGITAL

    def test_fotos_sao_hibridas(self):
        # págs. 33-34 (FOTO5): scan + 61 chars de moldura
        for i in (32, 33):
            tipo, _, _ = _classificar(EX1, i)
            assert tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR


@pytest.mark.skipif(not EX1.exists(), reason="exemplos/ex1.pdf ausente")
def test_embutir_ocr_recupera_hibrida_deficiente(tmp_path):
    """Integração (atl.md §7): em ex1.pdf, o modo auto precisa rodar OCR nas
    páginas híbridas deficientes SEM destruir a moldura existente (aditivo).
    Requer Tesseract; roda só 3 páginas para não demorar."""
    try:
        lang, cfg = nucleo._preparar_ocr()
    except Exception:
        pytest.skip("Tesseract indisponivel")
    # recorte com pág. 1 (separação, nativa), 2 (híbrida deficiente) e
    # 23 (híbrida NÃO deficiente) — 0-based 0, 1, 22
    alvo = tmp_path / "ex1_recorte.pdf"
    with pikepdf.open(EX1) as pdf:
        novo = pikepdf.new()
        for i in (0, 1, 22):
            novo.pages.append(pdf.pages[i])
        novo.save(alvo)
    n, info = nucleo.embutir_ocr(alvo, lang, cfg, workers=1,
                                 reocr_hibrido="auto")
    assert n >= 1                                  # antes da v2.10: 0
    assert info[0]["origem"] == "texto nativo"
    assert info[1]["origem"] == "OCR do LIMPAPDF"
    assert info[2]["origem"] == "camada e-proc reaproveitada"
    doc = pdfium.PdfDocument(str(alvo))
    tp = doc[1].get_textpage()
    t = tp.get_text_range() or ""
    tp.close()
    doc.close()
    assert len(t.strip()) > 400        # moldura (~264) + corpo do OCR
    assert "Evento 1" in t             # moldura preservada (aditivo!)


@pytest.mark.skipif(not EX1.exists(), reason="exemplos/ex1.pdf ausente")
def test_embutir_ocr_nunca_reusa_sem_ocr(tmp_path):
    """--reocr-hibrido=nunca: nenhuma página híbrida recebe OCR próprio."""
    try:
        lang, cfg = nucleo._preparar_ocr()
    except Exception:
        pytest.skip("Tesseract indisponivel")
    alvo = tmp_path / "ex1_recorte.pdf"
    with pikepdf.open(EX1) as pdf:
        novo = pikepdf.new()
        for i in (1, 22):
            novo.pages.append(pdf.pages[i])
        novo.save(alvo)
    n, info = nucleo.embutir_ocr(alvo, lang, cfg, workers=1,
                                 reocr_hibrido="nunca")
    assert n == 0
    assert info[0]["origem"] == "camada e-proc incompleta — revisar"
    assert info[1]["origem"] == "camada e-proc reaproveitada"


@pytest.mark.skipif(not SIG1.exists(), reason="exemplos/exemplo 1.pdf ausente")
def test_sig_nativo_nunca_deficiente():
    doc = pdfium.PdfDocument(str(SIG1))
    pdf = pikepdf.open(SIG1)
    try:
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            texto = (tp.get_text_range() or "").strip()
            tp.close()
            tipo, deficiente, _ = nucleo.classificar_pagina(page, doc[i],
                                                            texto)
            if tipo is nucleo.TipoPagina.NATIVA_DIGITAL:
                assert not deficiente
    finally:
        pdf.close()
        doc.close()
