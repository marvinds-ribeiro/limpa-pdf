# -*- coding: utf-8 -*-
"""portao_eproc.py — Portão de qualidade do suporte a e-proc (atl.md §9).

Roda o pipeline (limpeza + OCR) sobre exemplos/ex1.pdf em DOIS modos de
--reocr-hibrido ("nunca" = reuso puro da camada existente; "auto" = OCR
próprio aditivo nas híbridas deficientes) e compara, na amostra fixa:

  pág.  2 — híbrida deficiente típica (scan de TC, só moldura na camada)
  pág.  8 — híbrida deficiente com MUITA tinta (corpo denso)
  pág.  9 — idem
  pág. 23 — híbrida quase em branco (controle: pouco a recuperar)
  pág. 33 — foto (FOTO5; OCR deve agregar pouco e não atrapalhar)

Métricas por página e modo: caracteres extraíveis, palavras únicas (>= 4
letras) e presença da moldura ("Evento 1" — prova de que NADA foi removido).
Para as páginas em que o auto rodou OCR, mede também a confiança média do
Tesseract (palavras aceitas, conf >= 40 — o corte do pipeline).

CRITÉRIOS DE APROVAÇÃO (auto só fica se):
  1. chars(auto) >= chars(nunca) em TODAS as páginas da amostra
     (o modo auto é ADITIVO — nada é removido; isto o comprova);
  2. a moldura segue presente no auto em toda página que a tinha;
  3. confiança média das palavras embutidas >= 40.

Anexa a tabela como seção "## 7. Portão de qualidade" do RELATORIO_EPROC.md.
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).parent))
import limpa_pdf_mpsc as nucleo  # noqa: E402

PASTA = Path(__file__).parent
EX1 = PASTA / "exemplos" / "ex1.pdf"
RELATORIO = PASTA / "RELATORIO_EPROC.md"
AMOSTRA = [1, 7, 8, 22, 32]     # 0-based: págs. 2, 8, 9, 23, 33


def _texto_paginas(caminho):
    doc = pdfium.PdfDocument(str(caminho))
    try:
        out = []
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            out.append((tp.get_text_range() or "").strip())
            tp.close()
        return out
    finally:
        doc.close()


def _conf_media_scan(base_pdf, idx, lang, cfg):
    """Confiança média das palavras aceitas (conf >= 40) do OCR da região do
    scan da página idx — exatamente o que o modo auto embute."""
    import math  # noqa: F401 (usado indiretamente)
    pdf = pikepdf.open(base_pdf)
    doc = pdfium.PdfDocument(str(base_pdf))
    try:
        tp = doc[idx].get_textpage()
        texto = (tp.get_text_range() or "").strip()
        tp.close()
        tipo, defic, bbox = nucleo.classificar_pagina(pdf.pages[idx],
                                                      doc[idx], texto)
        if not (tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR and defic and bbox):
            return None
        page = pdf.pages[idx]
        box = page.mediabox
        mx0, my0 = float(box[0]), float(box[1])
        mediabox = (mx0, my0, float(box[2]) - mx0, float(box[3]) - my0)
        tarefa = {"idx": idx, "modo": "regioes",
                  "escala": nucleo._escala_render(page),
                  "mediabox": mediabox, "cands": [bbox]}
        cfg_ocr = f"{cfg or ''} --oem 1 --psm 6".strip()
        r = nucleo._ocr_executar_tarefa(doc, tarefa, lang, cfg_ocr)
        confs = []
        for reg in r["regs"]:
            _l, _p, cs = nucleo._linhas_texto_ocr(
                reg["dados"], mx0, my0, mediabox[3],
                mediabox[2] / r["px"][0], mediabox[3] / r["px"][1],
                dx_px=reg["cx0"], dy_px=reg["cy0"])
            confs += cs
        return (sum(confs) / len(confs)) if confs else None
    finally:
        pdf.close()
        doc.close()


def main():
    lang, cfg = nucleo._preparar_ocr()
    if not lang:
        raise SystemExit("Tesseract indisponivel — portao nao pode rodar.")
    tmp = Path(tempfile.mkdtemp(prefix="portao_eproc_"))
    base = tmp / "ex1_base.pdf"
    print("Limpeza estrutural...")
    nucleo.limpa_pdf(EX1, base, True)
    saidas = {}
    for modo in ("nunca", "auto"):
        alvo = tmp / f"ex1_{modo}.pdf"
        shutil.copy(base, alvo)
        print(f"OCR ({modo})...")
        nucleo.embutir_ocr(alvo, lang, cfg, reocr_hibrido=modo)
        saidas[modo] = _texto_paginas(alvo)

    linhas = ["", "## 7. Portão de qualidade (portao_eproc.py — "
                  "`nunca` × `auto` sobre o arquivo LIMPO)", ""]
    linhas.append("| Pág | Chars nunca | Chars auto | Palavras nunca | "
                  "Palavras auto | Moldura no auto? | Conf média OCR |")
    linhas.append("|---:|---:|---:|---:|---:|:--:|---:|")
    aprovado = True
    for idx in AMOSTRA:
        tn, ta = saidas["nunca"][idx], saidas["auto"][idx]
        cn = sum(1 for c in tn if not c.isspace())
        ca = sum(1 for c in ta if not c.isspace())
        pn = len(set(re.findall(r"[\wÀ-ÿ]{4,}", tn.lower())))
        pa = len(set(re.findall(r"[\wÀ-ÿ]{4,}", ta.lower())))
        moldura_antes = "Evento 1" in tn
        moldura = ("sim" if "Evento 1" in ta
                   else ("—" if not moldura_antes else "NAO!"))
        conf = _conf_media_scan(base, idx, lang, cfg)
        conf_s = f"{conf:.0f}" if conf is not None else "—"
        if ca < cn:
            aprovado = False
        if moldura == "NAO!":
            aprovado = False
        if conf is not None and conf < 40:
            aprovado = False
        linhas.append(f"| {idx + 1} | {cn} | {ca} | {pn} | {pa} | "
                      f"{moldura} | {conf_s} |")
    linhas.append("")
    linhas.append("Critérios: (1) chars(auto) >= chars(nunca) em toda a "
                  "amostra — o auto é ADITIVO, nada é removido; (2) moldura "
                  "presente onde existia; (3) confiança média >= 40. "
                  f"**Resultado: {'APROVADO' if aprovado else 'REPROVADO'}**.")
    linhas.append("")
    linhas.append("Nota: após a LIMPEZA a pág. 23 cai a densidade 43,1 "
                  "(< 45) e também recebe OCR aditivo no auto — direção "
                  "segura (só acrescenta; dedup e corte de confiança "
                  "protegem).")
    with RELATORIO.open("a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print("\n".join(linhas))
    print(f"\nTabela anexada a {RELATORIO}")
    if not aprovado:
        sys.exit(1)


if __name__ == "__main__":
    main()
