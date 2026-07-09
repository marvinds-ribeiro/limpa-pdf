"""Testes da exportação em Markdown (v2.8) — estrutura, peças e tabelas."""
import pikepdf
from pathlib import Path

import limpa_pdf_mpsc as core


def _pdf_texto(path: Path, paginas_texto: list):
    """PDF sintético com texto Helvetica extraível (uma string por página)."""
    pdf = pikepdf.new()
    for txt in paginas_texto:
        page = pdf.add_blank_page(page_size=(612, 792))
        fonte = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
            Encoding=pikepdf.Name.WinAnsiEncoding))
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=fonte))
        ops = [b"BT /F1 12 Tf 72 720 Td 14 TL"]
        for lin in txt.splitlines():
            s = (lin.encode("cp1252", "replace")
                 .replace(b"\\", b"\\\\").replace(b"(", b"\\(")
                 .replace(b")", b"\\)"))
            ops.append(b"(" + s + b") Tj T*")
        ops.append(b"ET")
        page.Contents = pdf.make_stream(b"\n".join(ops))
    pdf.save(path)


def test_detectar_peca_conservador():
    assert core._detectar_peca("DESPACHO") == "DESPACHO"
    assert core._detectar_peca("  TERMO DE DECLARACOES  ") == "TERMO DE DECLARACOES"
    assert core._detectar_peca("OFÍCIO Nº 123/2026") == "OFÍCIO Nº 123/2026"
    # prosa nunca vira heading
    assert core._detectar_peca("o despacho foi proferido ontem") is None
    assert core._detectar_peca("Despacho") is None             # não é MAIÚSCULA
    assert core._detectar_peca("DESPACHOU O JUIZ QUE") is None  # rótulo colado a letra
    assert core._detectar_peca("A" * 80) is None                # linha longa demais
    assert core._detectar_peca("") is None


def test_tabela_para_md_filtro_2x2():
    assert core._tabela_para_md([["a"], ["b"]]) is None          # 1 coluna
    assert core._tabela_para_md([["a", "b"]]) is None            # 1 linha
    md = core._tabela_para_md([["Nome", "Valor"], ["x", "1|2"]])
    assert md.splitlines()[0] == "| Nome | Valor |"
    assert "---" in md.splitlines()[1]
    assert "\\|" in md                                           # pipe escapado


def test_remover_sufixo_tolerante():
    assert core._remover_sufixo_tolerante("corpo aqui\nfim ocr", "fim  ocr") == "corpo aqui"
    assert core._remover_sufixo_tolerante("corpo aqui", "outro texto") is None


def test_exportar_md_estrutura(tmp_path):
    pdf = tmp_path / "doc.pdf"
    _pdf_texto(pdf, ["PORTARIA\ntexto da portaria", "pagina dois de texto corrido"])
    md = tmp_path / "doc.md"
    core.exportar_md(pdf, md, offset=1, total=2)
    t = md.read_text(encoding="utf-8")
    assert t.startswith("# doc")
    assert "**Total de páginas:** 2" in t
    assert "## Página 1 de 2" in t and "## Página 2 de 2" in t
    assert "### PORTARIA" in t
    assert "\n---\n" in t
    assert ">> AVISO" not in t and "REDE DE SEGURANCA" not in t
    assert "|" not in t.replace("\\|", "")   # sem pipes: nenhuma tabela válida


def test_exportar_md_pagina_sem_texto(tmp_path):
    pdf = tmp_path / "vazio.pdf"
    _pdf_texto(pdf, [""])
    md = tmp_path / "vazio.md"
    core.exportar_md(pdf, md)
    t = md.read_text(encoding="utf-8")
    assert "sem texto aproveitável" in t


def test_exportar_md_blocos_info_ocr(tmp_path):
    pdf = tmp_path / "img.pdf"
    _pdf_texto(pdf, ["texto de corpo da pagina"])
    md = tmp_path / "img.md"
    info = {0: {"blocos": [("conversa do whatsapp extraida", 85.0),
                           ("trecho ruim", 30.0)],
                "manuscrito": False}}
    core.exportar_md(pdf, md, offset=1, total=1, info_ocr=info)
    t = md.read_text(encoding="utf-8")
    assert "> **[Texto extraído de imagem na página 1]**" in t
    assert "> conversa do whatsapp extraida" in t
    assert t.count("baixa confiança de OCR") == 1   # só no bloco de conf 30


def test_exportar_md_manuscrito(tmp_path):
    pdf = tmp_path / "manu.pdf"
    _pdf_texto(pdf, ["texto ocr de manuscrito ruidoso aqui presente"])
    md = tmp_path / "manu.md"
    info = {0: {"blocos": [], "manuscrito": True}}
    core.exportar_md(pdf, md, info_ocr=info)
    t = md.read_text(encoding="utf-8")
    assert "Documento manuscrito — OCR de baixa confiança" in t


def test_exportar_md_offset_continuo(tmp_path):
    pdf = tmp_path / "parte.pdf"
    _pdf_texto(pdf, ["a", "b"])
    md = tmp_path / "parte.md"
    core.exportar_md(pdf, md, offset=151, total=300)
    t = md.read_text(encoding="utf-8")
    assert "## Página 151 de 300" in t and "## Página 152 de 300" in t
