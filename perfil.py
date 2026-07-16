#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perfil.py — perfil de desempenho do pipeline completo (Tarefa C.1).

Roda limpeza -> OCR -> numeração -> divisão -> exportação .md num PDF
representativo, cronometrando cada etapa (tempo total e s/página) e rodando
cProfile nas etapas pesadas (OCR e exportação). Gera um relatório .md com a
tabela de etapas e os hotspots de função — a base factual para decidir as
otimizações (nada de otimizar sem medir).

Uso:
  python perfil.py "exemplos/Apagou demais ORIGINAL.pdf" --saida PERFIL_ANTES.md
  python perfil.py grande.pdf --paginas 150   # fatia das primeiras N páginas
"""
import argparse
import cProfile
import io
import pstats
import shutil
import sys
import time
from pathlib import Path

import pikepdf

import limpa_pdf_mpsc as nucleo

# Funções cujo tempo cumulativo interessa no relatório (suspeitos do C.2).
HOTSPOTS_INTERESSE = (
    "image_to_data", "bilateralFilter", "render", "threshold",
    "_preparar_imagem_ocr", "_ocr_imagens_embutidas", "_elementos",
    "parse_content_stream", "unparse_content_stream", "find_tables",
    "extract_tables", "get_textpage", "save", "open",
    "_tabelas_md", "_extrair_paginas", "to_pil",
)


def _fatiar(origem: Path, destino: Path, n_pag: int):
    with pikepdf.open(origem) as pdf:
        if n_pag and n_pag < len(pdf.pages):
            novo = pikepdf.new()
            for p in pdf.pages[:n_pag]:
                novo.pages.append(p)
            novo.save(destino)
        else:
            shutil.copy2(origem, destino)


def _hotspots(profile: cProfile.Profile, limite=25):
    s = io.StringIO()
    st = pstats.Stats(profile, stream=s)
    st.sort_stats("cumulative")
    linhas = []
    for (arq, lin, nome), (cc, nc, tt, ct, _cal) in st.stats.items():
        if any(h in nome for h in HOTSPOTS_INTERESSE):
            linhas.append((ct, tt, nc, nome, Path(arq).name if arq else ""))
    linhas.sort(key=lambda x: -x[0])
    return linhas[:limite]


def main():
    ap = argparse.ArgumentParser(description="Perfil do pipeline (Tarefa C)")
    ap.add_argument("pdf", nargs="?",
                    default="exemplos/Apagou demais ORIGINAL.pdf")
    ap.add_argument("--paginas", type=int, default=0,
                    help="usar só as N primeiras páginas (0 = todas)")
    ap.add_argument("--saida", default="PERFIL_ANTES.md")
    ap.add_argument("--sem-ocr", action="store_true",
                    help="pula a etapa de OCR (só limpeza/export)")
    args = ap.parse_args()

    origem = Path(args.pdf)
    trabalho = Path(__file__).parent / "_perfil_tmp"
    trabalho.mkdir(exist_ok=True)
    alvo = trabalho / origem.name
    _fatiar(origem, alvo, args.paginas)
    tam_mb = alvo.stat().st_size / 1048576.0
    with pikepdf.open(alvo) as p:
        n_pag = len(p.pages)
    print(f"Perfil: {alvo.name} — {n_pag} páginas, {tam_mb:.1f} MB")

    etapas = []          # (nome, segundos, unidades)
    perfis = {}          # nome -> cProfile

    def medir(nome, fn, unidades, com_profile=False):
        pr = cProfile.Profile() if com_profile else None
        t0 = time.perf_counter()
        if pr:
            pr.enable()
        try:
            return fn()
        finally:
            if pr:
                pr.disable()
                perfis[nome] = pr
            dt = time.perf_counter() - t0
            etapas.append((nome, dt, unidades))
            print(f"  {nome:20s} {dt:8.1f} s  ({dt / max(unidades, 1):.2f} s/pág)")

    destino = trabalho / (alvo.stem + "_limpo.pdf")
    medir("limpa_pdf", lambda: nucleo.limpa_pdf(alvo, destino, True), n_pag)

    info_ocr = {}
    if not args.sem_ocr:
        lang, cfg = nucleo._preparar_ocr()
        if lang:
            def _ocr():
                nonlocal info_ocr
                n, info_ocr = nucleo.embutir_ocr(destino, lang, cfg)
                return n
            medir("embutir_ocr", _ocr, n_pag, com_profile=True)
        else:
            print("  [aviso] Tesseract indisponível; OCR pulado.")

    with pikepdf.open(destino) as p:
        total_pag = len(p.pages)
    medir("numerar_paginas",
          lambda: nucleo.numerar_paginas(destino, total_pag, 1), n_pag)
    partes = medir("dividir_pdf",
                   lambda: nucleo.dividir_pdf(destino, nucleo.MAX_MB_PARTE),
                   n_pag)

    def _exportar():
        for parte, offset in partes:
            nucleo.exportar_md(parte, parte.with_suffix(".md"),
                               offset=offset, total=total_pag,
                               info_ocr=info_ocr)
    medir("exportar_md", _exportar, n_pag, com_profile=True)

    # ------------------------- relatório -------------------------
    total = sum(dt for _n, dt, _u in etapas)
    L = [f"# Perfil de desempenho — `{alvo.name}`\n",
         f"**Páginas:** {n_pag} · **Tamanho:** {tam_mb:.1f} MB · "
         f"**Tempo total do pipeline:** {total:.1f} s "
         f"({total / 60:.1f} min)\n",
         "## Tempo por etapa\n",
         "| etapa | tempo total (s) | s/página | % do total |",
         "| --- | ---: | ---: | ---: |"]
    for nome, dt, u in etapas:
        L.append(f"| {nome} | {dt:.1f} | {dt / max(u, 1):.2f} | "
                 f"{dt / total * 100:.1f}% |")
    L.append("")
    for nome, pr in perfis.items():
        L.append(f"## Hotspots (cProfile) — {nome}\n")
        L.append("| função | tempo cumulativo (s) | tempo próprio (s) | chamadas |")
        L.append("| --- | ---: | ---: | ---: |")
        for ct, tt, nc, fn, arq in _hotspots(pr):
            L.append(f"| `{fn}` ({arq}) | {ct:.1f} | {tt:.1f} | {nc} |")
        L.append("")
    Path(args.saida).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nRelatório gravado em {args.saida}")


if __name__ == "__main__":
    main()
