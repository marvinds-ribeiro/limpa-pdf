#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auditoria_limpeza.py — auditoria da limpeza do limpa_pdf_mpsc (Tarefa A).

Roda a limpeza SEM SALVAR e mede, página a página, QUAL REGRA removeu O QUÊ:
para cada página e cada motivo de remoção (vide _motivo_remocao no módulo
principal), reconstrói a página removendo SÓ os elementos daquele motivo,
extrai o texto (pypdfium2) e compara com o original — medição REAL de
caracteres perdidos, não estimativa. Também faz o diff de texto extraído
ORIGINAL × LIMPO para cruzar as perdas.

Uso:
  python auditoria_limpeza.py --auditar "exemplos/Apagou demais ORIGINAL.pdf" ^
      --limpo "exemplos/Apagou demais LIMPO.pdf" --saida RELATORIO_APAGOU_DEMAIS.md
"""
import argparse
import difflib
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

import pikepdf
from pikepdf import unparse_content_stream

import limpa_pdf_mpsc as nucleo

# Máximo de trechos exibidos por motivo no relatório (o resto é resumido).
MAX_TRECHOS_MOTIVO = 120


def _texto_pdf_bytes(dados: bytes):
    """Texto de cada página de um PDF em memória (pypdfium2)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(dados)
    try:
        out = []
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            out.append(tp.get_text_range() or "")
            tp.close()
        return out
    finally:
        doc.close()


def _texto_paginas(pdf_path: Path):
    return _texto_pdf_bytes(pdf_path.read_bytes())


def _pagina_variante(pdf, page, els, remover_ix) -> bytes:
    """Serializa um PDF de 1 página igual a 'page', mas sem os elementos de
    índices 'remover_ix'. Não altera o documento de origem: a página é
    copiada para um doc novo e o content stream é trocado só na cópia."""
    novas = []
    for i, (_kind, _key, _bbox, instrs, _rot) in enumerate(els):
        if i not in remover_ix:
            novas.extend(instrs)
    novo = pikepdf.new()
    novo.pages.append(page)
    novo.pages[0].Contents = novo.make_stream(unparse_content_stream(novas))
    buf = io.BytesIO()
    novo.save(buf)
    return buf.getvalue()


def _montar_ctx(pdf, page, idx, boiler, boiler_base_P, cortes, faixas_base,
                sem_cabecalho, els):
    """Replica o contexto que reescrever() monta antes de decidir remoções
    (mesma lógica, mesmos parâmetros) para podermos consultar _motivo_remocao
    elemento a elemento sem reescrever a página."""
    g = nucleo._grupo(page)
    W, H = g
    cut_topo, cut_base = cortes.get(idx, (None, None))
    tiras_corpo = nucleo._tiras_corpo(els, W, H)
    drop_ix = set()
    spans_rem = []
    if sem_cabecalho:
        for lk, ixs, span in nucleo._clusters_topo(els, H):
            if (g, lk) in boiler:
                drop_ix.update(ixs)
                spans_rem.append(span)
    faixa_assin = nucleo._faixa_assinatura_vetorial(els, W, H) if sem_cabecalho else None
    ctx = {
        "g": g, "W": W, "H": H, "cut_topo": cut_topo, "cut_base": cut_base,
        "sem_cabecalho": sem_cabecalho, "drop_ix": drop_ix,
        "spans_rem": spans_rem, "faixa_assin": faixa_assin,
        "tiras_corpo": tiras_corpo, "boiler": boiler,
        "boiler_base_P": boiler_base_P, "faixas_base": faixas_base,
    }
    if hasattr(nucleo, "zonas_tabela"):
        ctx["zonas_tabela"] = nucleo.zonas_tabela(els, W, H) if sem_cabecalho else []
    return ctx


def _linhas_norm(texto: str):
    """Linhas do texto com espaçamento normalizado (p/ diff tolerante)."""
    return [" ".join(l.split()) for l in (texto or "").splitlines()
            if l.strip()]


def _nchars(texto: str) -> int:
    return sum(1 for c in texto if not c.isspace())


def _diff_linhas(antes: str, depois: str):
    """Linhas presentes em 'antes' e ausentes de 'depois' (com repetição)."""
    la, ld = _linhas_norm(antes), _linhas_norm(depois)
    sm = difflib.SequenceMatcher(a=la, b=ld, autojunk=False)
    perdidas = []
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            perdidas.extend(la[i1:i2])
    return perdidas


def auditar(original: Path, limpo: Path | None, saida: Path):
    print(f"Auditando {original.name}...")
    texto_orig = _texto_paginas(original)

    # por página: {motivo: (chars_removidos, [trechos])}
    perda_pag = []
    # elementos removidos por página: [(motivo, kind, bbox)]
    remocoes_pag = []
    cortes_reg = {}
    boiler_reg = []

    with pikepdf.open(original) as pdf:
        boiler, boiler_base_P, cortes, faixas_base = nucleo.analisar(pdf)
        cortes_reg = dict(cortes)
        boiler_reg = sorted(
            (str(k[1]) for k in boiler), key=str)
        for idx, page in enumerate(pdf.pages):
            els = nucleo._elementos(page)
            if els is None:
                perda_pag.append({})
                remocoes_pag.append([])
                continue
            ctx = _montar_ctx(pdf, page, idx, boiler, boiler_base_P, cortes,
                              faixas_base, True, els)
            motivo_por_el = {}
            for i, (kind, key, bbox, _instrs, rot) in enumerate(els):
                m = nucleo._motivo_remocao(i, kind, key, bbox, rot, ctx)
                if m:
                    motivo_por_el[i] = (m, kind, bbox)
            remocoes_pag.append(
                [(m, k, b) for m, k, b in motivo_por_el.values()])
            if not motivo_por_el:
                perda_pag.append({})
                continue
            # mede a perda REAL de cada motivo: remove só os elementos daquele
            # motivo e extrai o texto da página resultante. Também soma a
            # ÁREA de imagens removidas (em página escaneada o conteúdo está
            # nas imagens — chars não medem nada).
            area_pag = (ctx["W"] * ctx["H"]) or 1
            por_motivo = defaultdict(set)
            for i, (m, _k, _b) in motivo_por_el.items():
                por_motivo[m].add(i)
            res = {}
            for m, ixs in por_motivo.items():
                dados = _pagina_variante(pdf, page, els, ixs)
                t_sem = _texto_pdf_bytes(dados)[0]
                removidos = _nchars(texto_orig[idx]) - _nchars(t_sem)
                trechos = _diff_linhas(texto_orig[idx], t_sem)
                area = sum(
                    max(0.0, (els[i][2][2] - els[i][2][0])
                        * (els[i][2][3] - els[i][2][1])) / area_pag
                    for i in ixs
                    if els[i][0] in ("I", "II") and els[i][2])
                res[m] = (removidos, trechos, area)
            perda_pag.append(res)
            tot = sum(r[0] for r in res.values())
            tot_area = sum(r[2] for r in res.values())
            if tot or tot_area >= 0.01:
                print(f"  pag {idx + 1}: {tot} chars,"
                      f" {tot_area * 100:.1f}% da area em imagens removidos"
                      f" ({', '.join(sorted(res))})")

    # ---------------- diff ORIGINAL x LIMPO (arquivo existente) -------------
    diff_limpo = []
    if limpo and limpo.is_file():
        texto_limpo = _texto_paginas(limpo)
        for i, t_orig in enumerate(texto_orig):
            t_lim = texto_limpo[i] if i < len(texto_limpo) else ""
            perdidas = _diff_linhas(t_orig, t_lim)
            if perdidas:
                diff_limpo.append((i + 1, perdidas))

    _escrever_relatorio(saida, original, limpo, texto_orig, perda_pag,
                        remocoes_pag, cortes_reg, boiler_reg, diff_limpo)
    print(f"Relatorio gravado em {saida}")


def _escrever_relatorio(saida, original, limpo, texto_orig, perda_pag,
                        remocoes_pag, cortes_reg, boiler_reg, diff_limpo):
    L = []
    L.append("# Relatório de auditoria — \"apagou demais\"\n")
    L.append(f"**Arquivo:** `{original.name}` · "
             f"**Páginas:** {len(texto_orig)}\n")
    L.append("A limpeza foi executada SEM salvar; para cada página e cada "
             "motivo de remoção, a página foi reconstruída sem os elementos "
             "daquele motivo e o texto foi reextraído (pypdfium2). Os números "
             "abaixo são perda REAL de caracteres (não brancos), medida — "
             "não estimada.\n")

    # ------- ranking global -------
    total_por_motivo = defaultdict(int)
    area_por_motivo = defaultdict(float)
    paginas_por_motivo = defaultdict(set)
    for idx, res in enumerate(perda_pag):
        for m, (n, _t, a) in res.items():
            total_por_motivo[m] += n
            area_por_motivo[m] += a
            if n or a >= 0.01:
                paginas_por_motivo[m].add(idx + 1)
    total_chars_doc = sum(_nchars(t) for t in texto_orig)
    L.append("## 1. Ranking global — perda por motivo\n")
    L.append("(área = soma, em páginas inteiras equivalentes, das imagens "
             "removidas — em documento escaneado o conteúdo está nas imagens)\n")
    L.append("| motivo | chars removidos | % do texto do documento | "
             "área de imagens removida (págs equiv.) | páginas atingidas |")
    L.append("| --- | ---: | ---: | ---: | --- |")
    ordem = sorted(total_por_motivo,
                   key=lambda m: -(total_por_motivo[m] + area_por_motivo[m] * 1000))
    for m in ordem:
        n = total_por_motivo[m]
        pags = sorted(paginas_por_motivo[m])
        s_pags = ", ".join(map(str, pags[:20])) + (" ..." if len(pags) > 20 else "")
        L.append(f"| `{m}` | {n} | {n / max(total_chars_doc, 1) * 100:.2f}% "
                 f"| {area_por_motivo[m]:.2f} | {s_pags} |")
    L.append("")

    # ------- tabela por página -------
    L.append("## 2. Perda por página e por motivo\n")
    L.append("(só páginas com remoção; % relativa ao texto/área da página)\n")
    L.append("| pág | chars da pág | motivo | chars removidos | % da pág | "
             "área de imagens removida |")
    L.append("| ---: | ---: | --- | ---: | ---: | ---: |")
    for idx, res in enumerate(perda_pag):
        npag = _nchars(texto_orig[idx])
        for m, (n, _t, a) in sorted(res.items(), key=lambda kv: -kv[1][0]):
            if n <= 0 and a < 0.01:
                continue
            L.append(f"| {idx + 1} | {npag} | `{m}` | {n} | "
                     f"{n / max(npag, 1) * 100:.1f}% | {a * 100:.1f}% |")
    L.append("")

    # ------- trechos removidos por motivo -------
    L.append("## 3. Texto efetivamente removido, por motivo\n")
    for m in ordem:
        trechos = []
        for idx, res in enumerate(perda_pag):
            if m in res:
                for t in res[m][1]:
                    trechos.append((idx + 1, t))
        if not trechos:
            continue
        L.append(f"### Motivo `{m}` — {len(trechos)} linha(s) removida(s)\n")
        for pag, t in trechos[:MAX_TRECHOS_MOTIVO]:
            L.append(f"- (pág {pag}) `{t[:160]}`")
        if len(trechos) > MAX_TRECHOS_MOTIVO:
            L.append(f"- ... e mais {len(trechos) - MAX_TRECHOS_MOTIVO} linha(s)")
        L.append("")

    # ------- diff ORIGINAL x LIMPO -------
    if limpo:
        L.append(f"## 4. Diff de texto extraído — `{original.name}` × `{limpo.name}`\n")
        if not diff_limpo:
            L.append("Nenhuma linha perdida.\n")
        else:
            tot = sum(len(p) for _i, p in diff_limpo)
            L.append(f"{tot} linha(s) do ORIGINAL não aparecem no LIMPO:\n")
            for pag, perdidas in diff_limpo:
                L.append(f"### Página {pag} — {len(perdidas)} linha(s) perdida(s)\n")
                for t in perdidas[:80]:
                    L.append(f"- `{t[:160]}`")
                if len(perdidas) > 80:
                    L.append(f"- ... e mais {len(perdidas) - 80}")
                L.append("")

    # ------- dados auxiliares p/ hipóteses -------
    L.append("## 5. Dados auxiliares (verificação das hipóteses)\n")
    L.append("### Cortes de régua por página (analisar → cortes)\n")
    L.append("| pág | cut_topo (pt) | cut_topo/H | cut_base (pt) | cut_base/H |")
    L.append("| ---: | ---: | ---: | ---: | ---: |")
    # altura da página via pikepdf
    with pikepdf.open(original) as pdf:
        alturas = [nucleo._grupo(p)[1] for p in pdf.pages]
    for idx in sorted(cortes_reg):
        ct, cb = cortes_reg[idx]
        H = alturas[idx] or 1
        s_ct = f"{ct:.1f}" if ct is not None else "—"
        s_ctf = f"{ct / H:.3f}" if ct is not None else "—"
        s_cb = f"{cb:.1f}" if cb is not None else "—"
        s_cbf = f"{cb / H:.3f}" if cb is not None else "—"
        L.append(f"| {idx + 1} | {s_ct} | {s_ctf} | {s_cb} | {s_cbf} |")
    L.append("")
    L.append("### Chaves de boilerplate de TEXTO (forma normalizada, dígito→#)\n")
    so_digito = [k for k in boiler_reg
                 if k.startswith("('T'") and re.search(r"'[#\W ]*'\)$", k)]
    L.append(f"{len(boiler_reg)} chave(s) no total; "
             f"{len(so_digito)} com texto só de `#`/pontuação (suspeita H2):\n")
    for k in boiler_reg:
        marca = "  ⚠ só dígito/pontuação" if k in so_digito else ""
        L.append(f"- `{k}`{marca}")
    L.append("")

    saida.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Auditoria da limpeza (Tarefa A)")
    ap.add_argument("--auditar", required=True,
                    help="PDF ORIGINAL a auditar (a limpeza roda sem salvar)")
    ap.add_argument("--limpo", help="PDF LIMPO existente para o diff de texto")
    ap.add_argument("--saida", default="RELATORIO_APAGOU_DEMAIS.md",
                    help="arquivo .md do relatório")
    args = ap.parse_args()
    auditar(Path(args.auditar),
            Path(args.limpo) if args.limpo else None,
            Path(args.saida))


if __name__ == "__main__":
    main()
