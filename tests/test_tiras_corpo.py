"""Testes da proteção do corpo escaneado fatiado em tiras (Tarefa: regressão OCR).

Os PDFs do SIG frequentemente desenham a página escaneada como 2-3 TIRAS
horizontais de imagem (cada uma com ~100% da largura, mas 33-47% da altura).
A proteção antiga de "imagem de página inteira" exigia >= 80% da largura E da
altura POR IMAGEM, então nenhuma tira passava e os cortes de cabeçalho/rodapé
apagavam o corpo inteiro do documento (página em branco -> OCR de lixo).

Estes testes garantem que tiras que JUNTAS cobrem a página sobrevivem à
limpeza, sem impedir a remoção de banners decorativos rasos.
"""
import os
import shutil
from pathlib import Path

import pikepdf
from pikepdf import Name, Operator, parse_content_stream
import pytest

import limpa_pdf_mpsc as core

W, H = 595, 842  # A4 em pontos


def _pdf_com_tiras(caminho: Path, faixas):
    """Cria um PDF de 1 página com uma imagem XObject por faixa (y0, y1),
    cada uma cobrindo a largura toda — simula o scan fatiado do SIG."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(W, H))
    fluxo = []
    xobjs = pikepdf.Dictionary()
    for n, (y0, y1) in enumerate(faixas):
        img = pdf.make_stream(
            b"\x80", Type=Name.XObject, Subtype=Name.Image,
            Width=1, Height=1, ColorSpace=Name.DeviceGray, BitsPerComponent=8)
        xobjs[f"/Im{n}"] = img
        fluxo.append(f"q {W} 0 0 {y1 - y0:.2f} 0 {y0:.2f} cm /Im{n} Do Q")
    page.Resources = pikepdf.Dictionary(XObject=xobjs)
    page.Contents = pdf.make_stream(" ".join(fluxo).encode("latin-1"))
    pdf.save(caminho)


def _n_imagens_desenhadas(caminho: Path) -> int:
    with pikepdf.open(caminho) as pdf:
        return sum(1 for _ops, op in parse_content_stream(pdf.pages[0])
                   if op == Operator("Do"))


def test_scan_em_duas_tiras_sobrevive_a_limpeza(tmp_path):
    # Caso real do acervo (exemplo6): 2 tiras de ~47% da altura cada.
    orig = tmp_path / "scan.pdf"
    dest = tmp_path / "scan_limpo.pdf"
    _pdf_com_tiras(orig, [(0, H * 0.47), (H * 0.47, H * 0.94)])
    core.limpa_pdf(orig, dest, True)
    assert _n_imagens_desenhadas(dest) == 2


def test_scan_em_tres_tiras_sobrevive_a_limpeza(tmp_path):
    # Caso real do acervo (exemplo7): 3 tiras de ~33% da altura cada.
    orig = tmp_path / "scan.pdf"
    dest = tmp_path / "scan_limpo.pdf"
    _pdf_com_tiras(orig, [(0, H / 3), (H / 3, 2 * H / 3), (2 * H / 3, H)])
    core.limpa_pdf(orig, dest, True)
    assert _n_imagens_desenhadas(dest) == 3


def test_banner_raso_de_topo_continua_removivel(tmp_path):
    # Imagem larga mas RASA (5% da altura) colada no topo é decoração
    # (cabeçalho); a união vertical não chega perto de 80% da página, então a
    # proteção das tiras NÃO deve impedir a remoção.
    orig = tmp_path / "banner.pdf"
    dest = tmp_path / "banner_limpo.pdf"
    _pdf_com_tiras(orig, [(H * 0.95, H)])
    core.limpa_pdf(orig, dest, True)
    assert _n_imagens_desenhadas(dest) == 0


def test_imagem_de_meia_pagina_nao_e_protegida_como_tira(tmp_path):
    # Uma única imagem larga de meia página (união = 50% < 80%) mantém o
    # comportamento atual (não entra na proteção das tiras). No miolo da
    # página ela sobrevive pelos cortes normais.
    orig = tmp_path / "meia.pdf"
    dest = tmp_path / "meia_limpo.pdf"
    _pdf_com_tiras(orig, [(H * 0.25, H * 0.75)])
    core.limpa_pdf(orig, dest, True)
    assert _n_imagens_desenhadas(dest) == 1


# --- preferência pelo tessdata_best embutido --------------------------------

def test_tessdata_embutido_encontra_o_best_do_repo():
    pasta = core._tessdata_embutido()
    assert pasta is not None
    assert (pasta / "por.traineddata").is_file()
    esperado = Path(core.__file__).resolve().parent / "assets" / "tessdata_best"
    assert pasta == esperado


def test_preparar_ocr_prefere_tessdata_best_embutido(monkeypatch):
    tem_tesseract = shutil.which("tesseract") or os.path.isfile(
        os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR\tesseract.exe"))
    if not tem_tesseract:
        pytest.skip("Tesseract não instalado nesta máquina")
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    lang, cfg = core._preparar_ocr()
    assert lang == "por"
    # O caminho do repo tem ESPAÇOS ("Limpa PDF - Code"); '--tessdata-dir
    # "..."' quebra no shlex não-posix do pytesseract no Windows (as aspas
    # viram parte do caminho). O tessdata embutido é apontado via
    # TESSDATA_PREFIX, imune a parsing de shell.
    assert os.environ.get("TESSDATA_PREFIX", "").endswith("tessdata_best")
    assert cfg == ""
    # Fumaça: o Tesseract carrega o 'por' de verdade com essa configuração.
    from PIL import Image, ImageDraw
    img = Image.new("L", (200, 60), 255)
    ImageDraw.Draw(img).text((10, 20), "teste", fill=0)
    import pytesseract
    pytesseract.image_to_string(img, lang=lang, config=cfg)  # não deve lançar
