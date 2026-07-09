"""Testes da divisão por TAMANHO em MB (v2.8) — crescer-gravar-medir."""
import os
import pikepdf
from pathlib import Path

import limpa_pdf_mpsc as core


def _pdf_pesado(path: Path, pesos_kb: list):
    """PDF sintético: cada página referencia um stream de bytes ALEATÓRIOS
    (incompressíveis) do peso pedido — simula páginas escaneadas densas."""
    pdf = pikepdf.new()
    for n, kb in enumerate(pesos_kb):
        page = pdf.add_blank_page(page_size=(612, 792))
        img = pdf.make_stream(os.urandom(kb * 1024))
        img.Type = pikepdf.Name.XObject
        img.Subtype = pikepdf.Name.Image
        img.Width = 1
        img.Height = 1
        img.ColorSpace = pikepdf.Name.DeviceGray
        img.BitsPerComponent = 8
        page.Resources = pikepdf.Dictionary(
            XObject=pikepdf.Dictionary(**{f"Im{n}": img}))
        page.Contents = pdf.make_stream(f"q /Im{n} Do Q".encode())
    pdf.save(path)


def _total_paginas(paths):
    tot = 0
    for p in paths:
        with pikepdf.open(p) as pdf:
            tot += len(pdf.pages)
    return tot


def test_divide_por_mb_sem_perder_paginas(tmp_path):
    alvo = tmp_path / "grande.pdf"
    _pdf_pesado(alvo, [200] * 15)          # ~3 MB total
    partes = core.dividir_pdf(alvo, 1)     # limite 1 MB (efetivo 0.9 MB)
    limite = int(1 * 1024 * 1024 * core.DIV_MARGEM_SEGURANCA)
    assert len(partes) > 1
    assert not alvo.exists()               # original substituído
    assert _total_paginas([p for p, _ in partes]) == 15   # NENHUMA página some
    for p, _off in partes:
        assert p.stat().st_size <= limite  # nenhuma parte acima do limite
    # offsets contínuos: offset da parte k = 1 + páginas das partes anteriores
    esperado = 1
    for p, off in partes:
        assert off == esperado
        with pikepdf.open(p) as pdf:
            esperado += len(pdf.pages)


def test_pagina_gigante_mantida_inteira(tmp_path, capsys):
    alvo = tmp_path / "gigante.pdf"
    _pdf_pesado(alvo, [100, 2000, 100])    # página 2 sozinha > 1 MB
    partes = core.dividir_pdf(alvo, 1)
    assert _total_paginas([p for p, _ in partes]) == 3
    saida = capsys.readouterr().out
    assert "mantida inteira" in saida      # avisou, não fracionou nem perdeu


def test_max_mb_zero_nao_divide(tmp_path):
    alvo = tmp_path / "peq.pdf"
    _pdf_pesado(alvo, [50, 50])
    assert core.dividir_pdf(alvo, 0) == [(alvo, 1)]
    assert alvo.exists()


def test_arquivo_menor_que_limite_nao_divide(tmp_path):
    alvo = tmp_path / "cabe.pdf"
    _pdf_pesado(alvo, [50, 50])
    assert core.dividir_pdf(alvo, 100) == [(alvo, 1)]
    assert alvo.exists()
