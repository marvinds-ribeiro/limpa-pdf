#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decisoes_ocr.py — baseline das DECISÕES de OCR por página (atl.md §9).

Replica a pré-passagem de embutir_ocr (SEM rodar OCR nenhum) e registra, por
PDF e por página, a decisão tomada:
  "pular"      — texto aproveitável e nenhuma imagem candidata a OCR de região;
  "regioes:N"  — texto aproveitável + N imagens embutidas candidatas;
  "pagina"     — sem texto aproveitável: OCR de página inteira.

Modos:
  --baseline   grava decisoes_baseline.json com o comportamento atual;
  (sem flag)   compara com o baseline e FALHA (exit 1) se QUALQUER decisão de
               um arquivo do SIG mudou. Mudanças em arquivos não-SIG (ex1.pdf
               do e-proc) são reportadas como [mudanca esperada] — o objetivo
               da v2.10 é justamente mudá-las; depois de validadas, regrave o
               baseline.
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import pikepdf                    # noqa: E402
import pypdfium2 as pdfium        # noqa: E402
import limpa_pdf_mpsc as nucleo   # noqa: E402

EXEMPLOS = RAIZ / "exemplos"
BASELINE = Path(__file__).parent / "decisoes_baseline.json"
# Arquivos do SIG: decisão NUNCA pode mudar (regra 1 do atl.md).
SIG = {f"exemplo{n}.pdf" for n in range(2, 10)} | {"exemplo 1.pdf",
                                                   "Apagou demais ORIGINAL.pdf"}


def decidir_paginas(pdf_path: Path) -> dict:
    """Decisão da pré-passagem de embutir_ocr, POR página, sem rodar OCR.

    Usa nucleo.decisao_ocr_pagina() quando existir (v2.10+, espelha o
    classificador); senão reproduz a lógica da v2.9 (só
    _texto_e_aproveitavel + _imagem_candidata_ocr)."""
    out = {}
    pdf = pikepdf.open(pdf_path)
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            existente = (tp.get_text_range() or "").strip()
            tp.close()
            if hasattr(nucleo, "decisao_ocr_pagina"):
                out[str(i)] = nucleo.decisao_ocr_pagina(page, doc[i],
                                                        existente)
                continue
            els = nucleo._elementos(page)
            W, H = nucleo._grupo(page)
            if nucleo._texto_e_aproveitavel(existente):
                cands = [b for kind, _k, b, _ins, rot in (els or [])
                         if kind in ("I", "II") and b and not rot
                         and nucleo._imagem_candidata_ocr(b, W, H)]
                out[str(i)] = f"regioes:{len(cands)}" if cands else "pular"
            else:
                out[str(i)] = "pagina"
    finally:
        pdf.close()
        doc.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true",
                    help="grava decisoes_baseline.json com o comportamento"
                         " atual")
    args = ap.parse_args()
    atual = {}
    for p in sorted(EXEMPLOS.glob("*.pdf")):
        if "limpo" in p.stem.lower():
            continue
        atual[p.name] = decidir_paginas(p)
        print(f"  decidido: {p.name} ({len(atual[p.name])} pags)")
    if args.baseline:
        BASELINE.write_text(json.dumps(atual, indent=1), encoding="utf-8")
        print(f"\nBaseline de decisoes gravado em {BASELINE}")
        return
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    falhas = []
    for nome, pags in base.items():
        for pag, dec in pags.items():
            nova = atual.get(nome, {}).get(pag)
            if nova != dec:
                msg = f"{nome} pag {int(pag) + 1}: {dec} -> {nova}"
                if nome in SIG:
                    falhas.append(msg)
                else:
                    print(f"[mudanca esperada] {msg}")
    print()
    if falhas:
        for f in falhas:
            print(f"[FALHA SIG] {f}")
        print(f"\nREGRESSAO DE DECISAO: {len(falhas)} falha(s).")
        sys.exit(1)
    print("OK: decisoes do SIG identicas ao baseline.")


if __name__ == "__main__":
    main()
