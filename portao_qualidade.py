#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portao_qualidade.py — portão de qualidade de OCR (Tarefa C.4).

Compara, numa amostra de páginas, o OCR produzido pelo caminho ANTES
(implementação v2.8, congelada aqui dentro) e pelo caminho DEPOIS (o que
estiver em limpa_pdf_mpsc no momento). Critérios de aprovação (C.4):

  - total de caracteres reconhecidos: depois >= antes * 0,999
  - confiança média do Tesseract:      depois >= antes - 0,5
  - diff palavra a palavra: sem perda sistemática (relatadas as diferenças)

Uso:
  python portao_qualidade.py "exemplos/Apagou demais ORIGINAL.pdf" --paginas 30
"""
import argparse
import sys
import time
from pathlib import Path

import pypdfium2 as pdfium
import pytesseract

import limpa_pdf_mpsc as nucleo


# ------------- caminho ANTES (v2.8, congelado p/ comparação) -----------------

def _render_antes(pag, escala):
    """v2.8: render RGB -> PIL (a conversão p/ cinza acontece no preparo)."""
    return pag.render(scale=escala).to_pil()


def _preparar_antes(img):
    """v2.8: cinza -> bilateralFilter na resolução PLENA -> Otsu."""
    from PIL import Image
    import cv2
    import numpy as np
    arr = np.array(img.convert("L"))
    arr = cv2.bilateralFilter(arr, d=5, sigmaColor=40, sigmaSpace=40)
    _, bin_arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(bin_arr)


# ------------- caminho DEPOIS (o que estiver no módulo) ----------------------

def _render_depois(pag, escala):
    if getattr(nucleo, "OCR_RENDER_CINZA", False):
        return pag.render(scale=escala, grayscale=True).to_pil()
    return pag.render(scale=escala).to_pil()


def _ocr(img, lang, cfg):
    dados = pytesseract.image_to_data(
        img, lang=lang, config=cfg, output_type=pytesseract.Output.DICT)
    palavras, confs = [], []
    for j in range(len(dados["text"])):
        w = (dados["text"][j] or "").strip()
        try:
            c = int(float(dados["conf"][j]))
        except Exception:
            c = -1
        if w and c >= 40:          # mesmo corte usado na camada invisível
            palavras.append(w)
            confs.append(c)
    return palavras, confs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?",
                    default="exemplos/Apagou demais ORIGINAL.pdf")
    ap.add_argument("--paginas", type=int, default=30,
                    help="tamanho da amostra (páginas espaçadas do PDF)")
    args = ap.parse_args()

    lang, cfg = nucleo._preparar_ocr()
    if not lang:
        sys.exit("Tesseract indisponível.")
    cfg_ocr = f"{cfg or ''} --oem 1 --psm 6".strip()

    doc = pdfium.PdfDocument(str(Path(args.pdf)))
    n = len(doc)
    passo = max(1, n // args.paginas)
    amostra = list(range(0, n, passo))[:args.paginas]
    print(f"Amostra: {len(amostra)} páginas de {Path(args.pdf).name}")

    tot_a = tot_d = 0
    confs_a, confs_d = [], []
    t_a = t_d = 0.0
    difs = []
    import pikepdf
    pdf = pikepdf.open(str(Path(args.pdf)))
    for i in amostra:
        escala = nucleo._escala_render(pdf.pages[i])
        t0 = time.perf_counter()
        img_a = _preparar_antes(_render_antes(doc[i], escala))
        pa, ca = _ocr(img_a, lang, cfg_ocr)
        t_a += time.perf_counter() - t0
        t0 = time.perf_counter()
        img_d = nucleo._preparar_imagem_ocr(_render_depois(doc[i], escala))
        pd_, cd = _ocr(img_d, lang, cfg_ocr)
        t_d += time.perf_counter() - t0
        tot_a += sum(len(w) for w in pa)
        tot_d += sum(len(w) for w in pd_)
        confs_a += ca
        confs_d += cd
        if pa != pd_:
            so_a = [w for w in pa if w not in pd_]
            so_d = [w for w in pd_ if w not in pa]
            difs.append((i + 1, so_a[:12], so_d[:12]))
        print(f"  pag {i + 1:3d}: antes {sum(len(w) for w in pa):5d} ch"
              f" conf {sum(ca) / max(len(ca), 1):5.1f} |"
              f" depois {sum(len(w) for w in pd_):5d} ch"
              f" conf {sum(cd) / max(len(cd), 1):5.1f}", flush=True)
    doc.close()
    pdf.close()

    ca_m = sum(confs_a) / max(len(confs_a), 1)
    cd_m = sum(confs_d) / max(len(confs_d), 1)
    print("\n================ PORTÃO DE QUALIDADE ================")
    print(f"caracteres: antes {tot_a} | depois {tot_d}"
          f" ({tot_d / max(tot_a, 1) * 100:.2f}%) — exige >= 99,9%")
    print(f"confiança média: antes {ca_m:.2f} | depois {cd_m:.2f}"
          f" — exige >= antes - 0,5")
    print(f"tempo de render+preparo+OCR: antes {t_a:.1f} s | depois {t_d:.1f} s")
    if difs:
        print(f"\npáginas com diferença palavra a palavra: {len(difs)}")
        for pag, so_a, so_d in difs[:10]:
            print(f"  pag {pag}: só-antes={so_a} só-depois={so_d}")
    ok = tot_d >= tot_a * 0.999 and cd_m >= ca_m - 0.5
    print("\nRESULTADO:", "APROVADO" if ok else "REPROVADO")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
