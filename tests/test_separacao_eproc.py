# -*- coding: utf-8 -*-
"""Testes da correção "página de separação em branco" (v2.10.1).

Causa-raiz (RELATORIO_EPROC.md §8): o e-proc seleciona fontes em blocos
`BT /F1 10.00 Tf ET` ISOLADOS (sem texto mostrado); o texto vem em blocos
seguintes que herdam a fonte do estado gráfico. Esses blocos só-estado
repetiam entre páginas, viravam `boiler_texto` e eram removidos — o texto
MANTIDO ficava órfão de fonte e a página renderizava/extraía NADA.

Regra da correção: elemento "T" que não MOSTRA nenhum caractere é ESTADO,
não conteúdo — nunca é removido (remover não ganha nada; pode órfãozar o
texto seguinte). Preservação conservadora, CLAUDE.md §5.
"""
import sys
import tempfile
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import limpa_pdf_mpsc as nucleo  # noqa: E402

EX1 = RAIZ / "exemplos" / "ex1.pdf"


@pytest.mark.skipif(not EX1.exists(), reason="exemplos/ex1.pdf ausente")
def test_pagina_separacao_sobrevive_a_limpeza(tmp_path):
    """A página de separação do e-proc (pág. 1) tem de sair da limpeza com o
    conteúdo legível: texto extraível E tinta renderizada."""
    destino = tmp_path / "ex1_limpo.pdf"
    nucleo.limpa_pdf(EX1, destino, True)
    doc = pdfium.PdfDocument(str(destino))
    try:
        tp = doc[0].get_textpage()
        texto = tp.get_text_range() or ""
        tp.close()
        img = doc[0].render(scale=0.5).to_pil().convert("L")
        hist = img.histogram()
        tinta = sum(hist[:200]) / (img.width * img.height)
    finally:
        doc.close()
    # antes da correção: 16 chars e tinta 0.000 (página em branco)
    assert "AUTO DE PRIS" in texto          # conteúdo real preservado
    assert "5000082-11.2025" in texto       # nº do processo preservado
    assert tinta > 0.001                    # a página RENDERIZA algo


def _pdf_tf_orfao(caminho: Path):
    """PDF sintético com o padrão do e-proc: fonte selecionada num bloco
    BT/ET separado, texto no bloco seguinte (2 páginas iguais para o
    detector de repetição ter com o que trabalhar)."""
    pdf = pikepdf.new()
    for _ in range(3):
        page = pdf.add_blank_page(page_size=(595, 842))
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(
            F1=pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica))))
        fluxo = (b"BT /F1 12.00 Tf ET\n"
                 b"q 0 g BT 100 400 Td (CONTEUDO DO CORPO) Tj ET Q\n")
        page.Contents = pdf.make_stream(fluxo)
    pdf.save(caminho)


def test_bloco_tf_orfao_nunca_e_removido(tmp_path):
    """Bloco de texto que não mostra nenhum caractere (só Tf) é estado:
    a limpeza jamais o remove, mesmo repetido em todas as páginas."""
    origem = tmp_path / "sintetico.pdf"
    _pdf_tf_orfao(origem)
    destino = tmp_path / "sintetico_limpo.pdf"
    nucleo.limpa_pdf(origem, destino, True)
    with pikepdf.open(destino) as pdf:
        for page in pdf.pages:
            ops = [str(op) for _o, op in pikepdf.parse_content_stream(page)]
            assert ops.count("Tf") >= 1     # o Tf sobreviveu
    doc = pdfium.PdfDocument(str(destino))
    try:
        tp = doc[0].get_textpage()
        texto = tp.get_text_range() or ""
        tp.close()
    finally:
        doc.close()
    assert "CONTEUDO DO CORPO" in texto
