"""Testes do OCR por região de imagem embutida (v2.8) — filtro, dedup, camada."""
import limpa_pdf_mpsc as core

W, H = 612.0, 792.0


def _bbox_frac(frac, y0=200.0):
    """bbox com fração de área 'frac', fora da zona de cabeçalho."""
    w = W * 0.6
    h = frac * W * H / w
    return (50.0, y0, 50.0 + w, y0 + h)


def test_filtro_exclui_logo_e_pagina_inteira():
    # logo do MPSC medido: ~0.014 -> fora por fração mínima
    assert not core._imagem_candidata_ocr(_bbox_frac(0.014), W, H)
    # print de WhatsApp medido: 0.024-0.063 -> entra
    assert core._imagem_candidata_ocr(_bbox_frac(0.024), W, H)
    assert core._imagem_candidata_ocr(_bbox_frac(0.063), W, H)
    # página escaneada inteira (>= 0.80): já coberta pelo fluxo existente
    assert not core._imagem_candidata_ocr((0, 0, W, H * 0.9), W, H)


def test_filtro_exclui_zona_cabecalho():
    # imagem grande o bastante, mas colada no topo (15% superior)
    topo = H * (1 - core.IMG_OCR_ZONA_CABECALHO) + 1
    assert not core._imagem_candidata_ocr((50, topo, 350, topo + 100), W, H)


def test_texto_contido_tolerante():
    corpo = "Cuida-se de relatório sobre conversa mantida entre investigados"
    assert core._texto_contido("relatório sobre conversa investigados", corpo)
    assert not core._texto_contido(
        "mensagem inédita sobre transferência bancária", corpo)
    assert not core._texto_contido("", corpo)


def test_linhas_texto_ocr_com_deslocamento():
    dados = {"text": ["Oi"], "conf": ["90"], "left": [10], "top": [20],
             "width": [40], "height": [12]}
    # página inteira (sem deslocamento)
    l0, p0, c0 = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18)
    # mesmo dado vindo de um recorte deslocado 100px/50px
    l1, p1, c1 = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18,
                                        dx_px=100, dy_px=50)
    assert p0 == p1 == ["Oi"] and c0 == c1 == [90]
    assert l0 != l1                      # coordenadas mudaram
    assert b"(Oi) Tj" in l1[0]
    # conf < 40 é descartada (mesmo corte do PDF)
    dados["conf"] = ["30"]
    l2, p2, _ = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18)
    assert not l2 and not p2
