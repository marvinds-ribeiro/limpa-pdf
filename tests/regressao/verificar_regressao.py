#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar_regressao.py — regressão da limpeza (Tarefa A.5).

Dois modos:
  --baseline   roda a limpeza ATUAL sobre todos os PDFs de exemplos/ e grava
               baseline.json com, por PDF e por página:
                 - as CHAVES dos elementos de moldura removidos pelos motivos
                   CALIBRADOS (assinatura, carimbo, cluster/boiler, glifo,
                   canto) — remoções que NUNCA podem deixar de acontecer;
                 - tinta renderizada do miolo (faixa 10%–90% da altura) da
                   página LIMPA — que nunca pode DIMINUIR (apagar mais);
                 - caracteres extraíveis da página LIMPA — idem.
  (sem flag)   roda a limpeza atual e compara com baseline.json:
               FALHA se (a) alguma remoção de moldura calibrada deixou de
               acontecer, ou (b) o miolo (tinta ou chars) piorou em qualquer
               página. Melhorar (preservar MAIS miolo) é aprovado e reportado.

Uso:
  python tests/regressao/verificar_regressao.py --baseline
  python tests/regressao/verificar_regressao.py
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import limpa_pdf_mpsc as nucleo  # noqa: E402
import pikepdf                    # noqa: E402

EXEMPLOS = RAIZ / "exemplos"
BASELINE = Path(__file__).parent / "baseline.json"
SAIDA = Path(__file__).parent / "_saida"

# Motivos de moldura CALIBRADOS: têm de continuar removendo os MESMOS
# elementos para sempre. (Os motivos geométricos corte_*/faixa_* ficam de
# fora de propósito: são as regras corrigidas na v2.9 — a proteção do miolo
# cobre o outro lado.)
MOTIVOS_MOLDURA = {
    "assinatura_rotacionada", "assinatura_vetorial", "carimbo_copia",
    "cluster_topo", "boiler_texto", "boiler_imagem", "boiler_path",
    "glifo_orfao", "canto_direito", "tarja_margem",
}
FAIXA_MIOLO = (0.10, 0.90)   # fração da altura considerada "miolo"
TOL_TINTA = 0.001            # tolerância absoluta de fração de tinta (ruído)


def _chave_el(kind, bbox):
    return f"{kind}:{round(bbox[0])}:{round(bbox[1])}:{round(bbox[2])}:{round(bbox[3])}"


def _montar_ctx(page, idx, analise, els):
    boiler, boiler_base_P, cortes, faixas_base = analise
    g = nucleo._grupo(page)
    W, H = g
    cut_topo, cut_base = cortes.get(idx, (None, None))
    tiras = nucleo._tiras_corpo(els, W, H)
    drop_ix = set(); spans = []
    for lk, ixs, span in nucleo._clusters_topo(els, H):
        if (g, lk) in boiler:
            drop_ix.update(ixs); spans.append(span)
    fa = nucleo._faixa_assinatura_vetorial(els, W, H)
    ctx = {"g": g, "W": W, "H": H, "cut_topo": cut_topo, "cut_base": cut_base,
           "sem_cabecalho": True, "drop_ix": drop_ix, "spans_rem": spans,
           "faixa_assin": fa, "tiras_corpo": tiras, "boiler": boiler,
           "boiler_base_P": boiler_base_P, "faixas_base": faixas_base}
    # zonas de tabela (v2.9); ausente na versão antiga ao gerar o baseline
    if hasattr(nucleo, "zonas_tabela"):
        ctx["zonas_tabela"] = nucleo.zonas_tabela(els, W, H)
    return ctx


def _molduras_removidas(pdf_path: Path):
    """{pagina: [chaves]} dos elementos removidos por motivos calibrados."""
    out = {}
    with pikepdf.open(pdf_path) as pdf:
        analise = nucleo.analisar(pdf)
        for idx, page in enumerate(pdf.pages):
            els = nucleo._elementos(page)
            if els is None:
                continue
            ctx = _montar_ctx(page, idx, analise, els)
            chaves = []
            for i, (kind, key, bbox, _ins, rot) in enumerate(els):
                m = nucleo._motivo_remocao(i, kind, key, bbox, rot, ctx)
                if m in MOTIVOS_MOLDURA and bbox:
                    chaves.append(_chave_el(kind, bbox))
            if chaves:
                out[str(idx)] = sorted(chaves)
    return out


def _elementos_presentes(pdf_path: Path):
    """{pagina: set(chaves)} dos elementos presentes num PDF (já limpo)."""
    out = {}
    with pikepdf.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            els = nucleo._elementos(page)
            if els is None:
                continue
            out[str(idx)] = {_chave_el(kind, bbox)
                             for kind, _k, bbox, _i, rot in els
                             if kind and bbox}
    return out


def _tinta_miolo(pdf_path: Path):
    """Fração de pixels não-brancos no miolo (10%–90% da altura), por página."""
    import numpy as np
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        out = []
        for i in range(len(doc)):
            arr = np.array(doc[i].render(scale=0.35).to_pil().convert("L"))
            h = arr.shape[0]
            mi = arr[int(h * (1 - FAIXA_MIOLO[1])):int(h * (1 - FAIXA_MIOLO[0])), :]
            out.append(round(float((mi < 220).mean()), 5))
        return out
    finally:
        doc.close()


def _chars_paginas(pdf_path: Path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        out = []
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            t = tp.get_text_range() or ""
            tp.close()
            out.append(sum(1 for c in t if not c.isspace()))
        return out
    finally:
        doc.close()


def coletar():
    """Roda a limpeza atual sobre exemplos/ e coleta as métricas."""
    SAIDA.mkdir(parents=True, exist_ok=True)
    dados = {}
    pdfs = [p for p in sorted(EXEMPLOS.glob("*.pdf")) if "LIMPO" not in p.stem]
    for pdf in pdfs:
        destino = SAIDA / pdf.name
        nucleo.limpa_pdf(pdf, destino, True)
        dados[pdf.name] = {
            "molduras": _molduras_removidas(pdf),
            "tinta_miolo": _tinta_miolo(destino),
            "chars": _chars_paginas(destino),
        }
        print(f"  coletado: {pdf.name}")
    return dados


def comparar(base, atual):
    falhas, melhoras = [], []
    for nome, b in base.items():
        a = atual.get(nome)
        if a is None:
            falhas.append(f"{nome}: PDF sumiu de exemplos/")
            continue
        # (a) moldura calibrada continua removida?
        presentes = _elementos_presentes(SAIDA / nome)
        for pag, chaves in b["molduras"].items():
            tem = presentes.get(pag, set())
            for ch in chaves:
                if ch in tem:
                    falhas.append(f"{nome} pag {int(pag)+1}: moldura voltou ({ch})")
        # (b) miolo não pode piorar
        for i, (tb, ta) in enumerate(zip(b["tinta_miolo"], a["tinta_miolo"])):
            if ta < tb - TOL_TINTA:
                falhas.append(f"{nome} pag {i+1}: tinta do miolo caiu"
                              f" {tb:.4f} -> {ta:.4f}")
            elif ta > tb + TOL_TINTA:
                melhoras.append(f"{nome} pag {i+1}: miolo preservado a mais"
                                f" (tinta {tb:.4f} -> {ta:.4f})")
        for i, (cb, ca) in enumerate(zip(b["chars"], a["chars"])):
            if ca < cb:
                falhas.append(f"{nome} pag {i+1}: chars cairam {cb} -> {ca}")
            elif ca > cb:
                melhoras.append(f"{nome} pag {i+1}: chars {cb} -> {ca}")
    return falhas, melhoras


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true",
                    help="grava baseline.json com o comportamento atual")
    args = ap.parse_args()
    dados = coletar()
    if args.baseline:
        BASELINE.write_text(json.dumps(dados, indent=1), encoding="utf-8")
        print(f"\nBaseline gravado em {BASELINE}")
        return
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    falhas, melhoras = comparar(base, dados)
    print()
    for m in melhoras:
        print(f"[melhora] {m}")
    print()
    if falhas:
        for f in falhas:
            print(f"[FALHA] {f}")
        print(f"\nREGRESSAO: {len(falhas)} falha(s).")
        sys.exit(1)
    print(f"OK: nenhuma regressao ({len(melhoras)} melhora(s) de preservacao).")


if __name__ == "__main__":
    main()
