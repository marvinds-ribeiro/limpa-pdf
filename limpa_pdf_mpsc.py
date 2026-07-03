#!/usr/bin/env python3
"""
limpa_pdf_mpsc.py — v2.7 — Limpeza em lote de PDFs exportados do SIG (Softplan/MPSC)

Remove, em qualquer layout (GAECO, CAT, Promotorias...):
  1. Assinatura digital vertical da margem (texto rotacionado OU vetorizado) — sempre
  2. Carimbo "CÓPIA/COPIADO" no canto (letras e moldura tracejada) — sempre
  3. Cabeçalhos e rodapés (texto, LOGOTIPOS/imagens e linhas), por detecção
     automática de elementos repetidos entre páginas e, em documentos curtos,
     pela régua separadora da própria página (--sem-cabecalho)

Extras:
  --txt  Exporta texto limpo (extração 100% Python; funciona no Windows)
  --ocr  Usa OCR (Tesseract) nas páginas sem texto aproveitável (corpo
         vetorizado/escaneado OU camada de texto corrompida), para que o
         .txt não perca informação

Novidades da v2.7:
  - PROTEÇÃO DO CORPO ESCANEADO FATIADO EM TIRAS: scans do SIG frequentemente
    vêm desenhados como 2-3 tiras horizontais de imagem (cada uma com ~100%
    da largura, mas 33-47% da altura). A proteção antiga de "imagem de página
    inteira" exigia >= 80% da largura E da altura POR IMAGEM, então nenhuma
    tira passava e os cortes de cabeçalho/rodapé apagavam o corpo inteiro do
    documento (página em branco -> OCR de lixo). Agora, se a união vertical
    das imagens largas cobre >= 80% da página, elas são o corpo escaneado e
    nunca são removidas (vide _tiras_corpo).
  - TESSDATA_BEST EMBUTIDO COM PRIORIDADE: o OCR passa a preferir o modelo
    por.traineddata do tessdata_best que acompanha o programa (assets/ no
    desenvolvimento, bundle do PyInstaller no app congelado) em vez do modelo
    FAST (quantizado) da instalação comum do Tesseract — apontado via
    TESSDATA_PREFIX, imune a caminhos com espaços (vide _tessdata_embutido).

Novidades da v2.6:
  - OCR FORÇADO EM CAMADA DE TEXTO CORROMPIDA: alguns PDFs do SIG trazem uma
    "camada de texto" cuja fonte não tem mapeamento Unicode (sem /ToUnicode);
    a extração devolve caracteres de controle/PUA (lixo) e o código antigo,
    vendo len>=20, PULAVA o OCR — despejando o lixo no .txt. Agora a qualidade
    do texto é medida (fração de alfanuméricos x fração de controle/PUA): se a
    página for majoritariamente lixo, a camada podre é REMOVIDA e a página vai
    ao OCR. O .txt também passa a mostrar o aviso de "página sem texto
    aproveitável" (em vez do lixo) quando o OCR não é usado.
  - CAP DE RENDER NO OCR: páginas com mediabox gigante (ex.: scans de
    2290x3286 pt) não geram mais imagens de >12000 px a 400 dpi; a escala é
    reduzida para um teto seguro, preservando memória e tempo.

Novidades da v2.5:
  - PAGINAÇÃO CONTÍNUA para referência por IA: cada página recebe, no canto
    superior direito, um número visível (Helvetica/Arial 10, preto) no formato
    "[Pagina N de TOTAL]". O mesmo número entra como camada de texto
    selecionável no PDF e no cabeçalho do .txt ("===== Pagina N ====="). A
    numeração é CONTÍNUA do 1 ao total do documento e é aplicada ANTES da
    divisão em partes (>150 páginas), de modo que NÃO reinicia a cada parte:
    a parte02 começa em 151, a parte03 em 301 etc. Desligável com --sem-numero.

Novidades da v2.4:
  - CABEÇALHO EM DOCUMENTOS CURTOS (1-2 páginas): despachos, portarias e
    pareceres com 1 página tinham o cabeçalho/rodapé preservados, porque a
    detecção dependia de repetição entre páginas (>= 3). Agora, em documentos
    de até 4 páginas, o corte é guiado pela RÉGUA SEPARADORA horizontal da
    própria página; sem régua, recorre a faixas fixas no topo e na base. O
    corte é estendido para englobar a linha do órgão colada logo abaixo da
    régua ("11ª Promotoria...", "Centro de Apoio...").
  - ASSINATURA DIGITAL VETORIZADA: além da assinatura como texto rotacionado,
    agora também é removida a assinatura desenhada como vetor (caminhos) numa
    coluna estreita e densa da margem — distinguida do texto de corpo
    justificado pela densidade de glifos, sem falsos positivos.
  - Os cortes de cabeçalho/rodapé passam a remover TODOS os tipos de elemento
    (texto, imagens/logos e caminhos), inclusive glifos órfãos (ex.: cedilha).

Novidades da v2.3:
  - Correção do ALINHAMENTO da camada de OCR: o texto invisível agora cai
    exatamente sobre as palavras da imagem (tamanho, espaçamento e posição
    corretos). Antes, em PDFs cujo conteúdo começa com um 'cm' (ex.:
    0.75 0 0 -0.75 0 H, comum no SIG), o texto saía condensado no topo da
    página. A camada passou a neutralizar esse CTM herdado e a calcular a
    escala horizontal pela largura real da fonte. O OCR também passou a
    renderizar a 300 dpi, melhorando o reconhecimento.

Uso:
  python limpa_pdf_mpsc.py "C:\\pasta" --sem-cabecalho --txt --ocr

Requisitos: pip install pikepdf pdfplumber pypdfium2 pytesseract
            (OCR requer também o programa Tesseract instalado)
"""

import argparse
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pikepdf
from pikepdf import Operator, parse_content_stream, unparse_content_stream

# ----------------------------- parâmetros -----------------------------------
TOL_ROT = 0.01          # tolerância p/ considerar texto rotacionado
ZONA_TOPO = 0.30        # fração superior da página onde boilerplate pode viver
ZONA_BASE = 0.12        # fração inferior
FRACAO_REPETICAO = 0.25 # elemento repetido em >= max(3, 25% das págs) = boilerplate
CANTO_X, CANTO_Y = 200, 230   # região do carimbo CÓPIA (canto sup. esquerdo)
MAX_PAGINAS = 150       # divide PDFs maiores que isso em partes (0 = não dividir)
# Faixas fixas (fallback p/ docs curtos, em pontos) — apenas TEXTO:
FAIXA_TOPO_TXT, FAIXA_BASE_TXT = 78, 70
CANTO_DIR_X, CANTO_DIR_Y = 400, 95

OPS_SHOW = {Operator("Tj"), Operator("TJ"), Operator("'"), Operator('"')}
OPS_CONSTR = {Operator(o) for o in ("m", "l", "c", "v", "y", "re", "h")}
OPS_PAINT = {Operator(o) for o in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n")}

I = (1, 0, 0, 1, 0, 0)

def mul(m, n):
    a, b, c, d, e, f = m; A, B, C, D, E, F = n
    return (a*A + b*C, a*B + b*D, c*A + d*C, c*B + d*D, e*A + f*C + E, e*B + f*D + F)

def pt(m, x, y):
    a, b, c, d, e, f = m
    return (a*x + c*y + e, b*x + d*y + f)

def norm_txt(operands, op):
    """Prefixo normalizado do texto exibido (dígitos -> #)."""
    parts = []
    try:
        if op == Operator("TJ"):
            for el in operands[0]:
                if isinstance(el, (pikepdf.String, str, bytes)):
                    parts.append(str(el))
        else:
            for el in operands:
                if isinstance(el, (pikepdf.String, str, bytes)):
                    parts.append(str(el))
    except Exception:
        pass
    s = "".join(parts)
    s = "".join("#" if ch.isdigit() else ch for ch in s if ch.isprintable())
    return s.strip().lower()[:14]


def _iter_elementos(page, colher):
    """Percorre o content stream rastreando CTM e matriz de texto.
    Chama colher(kind, key, bbox, instrucoes) para cada elemento candidato.
    kind: 'T' texto, 'P' caminho pintado, 'I' imagem XObject, 'II' imagem inline.
    Retorna a lista completa de instruções (para reescrita)."""
    try:
        instrs = list(parse_content_stream(page))
    except Exception:
        return None

    res = page.get("/Resources", {}) or {}
    xobjs = res.get("/XObject", {}) or {}
    _W, _H = _grupo(page)

    def _zona_img(bbox):
        if bbox[1] >= _H * (1 - ZONA_TOPO):
            return "T"
        if bbox[3] <= _H * ZONA_BASE:
            return "B"
        return "M"

    ctm = I
    pilha = []
    # estado de caminho
    buf_path, pts, tem_clip = [], [], False
    # estado de texto
    em_bt, buf_bt, tlm, tl = False, [], I, 0.0
    bt_rot, bt_pos, bt_txt = False, [], ""

    n = len(instrs)
    idx = 0
    while idx < n:
        operands, op = instrs[idx], None
        operands, op = instrs[idx][0], instrs[idx][1]
        item = instrs[idx]
        idx += 1

        if em_bt:
            buf_bt.append(item)
            if op == Operator("Tm") and len(operands) == 6:
                tlm = tuple(float(v) for v in operands)
            elif op in (Operator("Td"), Operator("TD")) and len(operands) == 2:
                tx, ty = float(operands[0]), float(operands[1])
                if op == Operator("TD"):
                    tl = -ty
                tlm = mul((1, 0, 0, 1, tx, ty), tlm)
            elif op == Operator("TL") and operands:
                tl = float(operands[0])
            elif op == Operator("T*"):
                tlm = mul((1, 0, 0, 1, 0, -tl), tlm)
            elif op in OPS_SHOW:
                if op in (Operator("'"), Operator('"')):
                    tlm = mul((1, 0, 0, 1, 0, -tl), tlm)
                m = mul(tlm, ctm)
                if abs(m[1]) > TOL_ROT or abs(m[2]) > TOL_ROT:
                    bt_rot = True
                bt_pos.append((m[4], m[5]))
                if not bt_txt:
                    bt_txt = norm_txt(operands, op)
            elif op == Operator("ET"):
                em_bt = False
                if bt_pos:
                    xs = [p[0] for p in bt_pos]; ys = [p[1] for p in bt_pos]
                    bbox = (min(xs), min(ys) - 2, max(xs) + 4, max(ys) + 10)
                else:
                    bbox = (0, 0, 0, 0)
                key = ("T", round((bbox[1]) / 4), bt_txt)
                colher("T", key, bbox, buf_bt, bt_rot)
            continue

        if op == Operator("BT"):
            em_bt, buf_bt, tlm = True, [item], I
            bt_rot, bt_pos, bt_txt, tl = False, [], "", 0.0
            continue

        # ------- fora de texto -------
        if op == Operator("q"):
            pilha.append(ctm)
        elif op == Operator("Q"):
            ctm = pilha.pop() if pilha else I
        elif op == Operator("cm") and len(operands) == 6:
            ctm = mul(tuple(float(v) for v in operands), ctm)

        if op in OPS_CONSTR:
            buf_path.append(item)
            vals = [float(v) for v in operands] if operands else []
            if op == Operator("re") and len(vals) == 4:
                x, y, w, h = vals
                for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                    pts.append(pt(ctm, px, py))
            else:
                for j in range(0, len(vals) - 1, 2):
                    pts.append(pt(ctm, vals[j], vals[j + 1]))
            continue
        if op in (Operator("W"), Operator("W*")):
            buf_path.append(item)
            tem_clip = True
            continue
        if op in OPS_PAINT:
            buf_path.append(item)
            if pts and not tem_clip:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                key = ("P", round(bbox[0] / 3), round(bbox[1] / 3),
                       round(bbox[2] / 3), round(bbox[3] / 3), len(pts), str(op))
                colher("P", key, bbox, buf_path, False)
            else:
                colher(None, None, None, buf_path, False)  # clip: manter sempre
            buf_path, pts, tem_clip = [], [], False
            continue

        if op == Operator("Do") and operands:
            nome = str(operands[0])
            sub = None
            try:
                xo = xobjs.get(operands[0])
                sub = str(xo.get("/Subtype")) if xo is not None else None
            except Exception:
                pass
            if sub == "/Image":
                cs = [pt(ctm, 0, 0), pt(ctm, 1, 0), pt(ctm, 0, 1), pt(ctm, 1, 1)]
                xs = [p[0] for p in cs]; ys = [p[1] for p in cs]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                key = ("I", round(bbox[0] / 3), round(bbox[2] / 3), _zona_img(bbox))
                colher("I", key, bbox, [item], False)
                continue
            colher(None, None, None, [item], False)
            continue

        if str(op) == "BI" or op == Operator("BI"):
            cs = [pt(ctm, 0, 0), pt(ctm, 1, 1)]
            xs = [p[0] for p in cs]; ys = [p[1] for p in cs]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            key = ("II", round(bbox[0] / 3), round(bbox[2] / 3), _zona_img(bbox))
            colher("II", key, bbox, [item], False)
            continue

        colher(None, None, None, [item], False)
    return True




def _elementos(page):
    """Uma única passada: devolve [(kind, key, bbox, instrs, rot), ...]."""
    out = []

    def colher(kind, key, bbox, instrs, rot):
        out.append((kind, key, bbox, instrs, rot))
    if _iter_elementos(page, colher) is None:
        return None
    return out


def _clusters_topo(els, H):
    """Agrupa glifos-caminho da zona superior em linhas. Devolve
    [(key_linha, set(indices), (x0, y, x1))]."""
    cand = []
    for i, (kind, key, bbox, instrs, rot) in enumerate(els):
        if kind == "P" and not rot and bbox and bbox[1] >= H * (1 - ZONA_TOPO) \
                and (bbox[3] - bbox[1]) <= 16:
            cand.append((i, bbox, key[5]))
    cand.sort(key=lambda e: (-e[1][1], e[1][0]))
    linhas = []
    for i, bbox, npts in cand:
        if linhas and abs(linhas[-1]["y"] - bbox[1]) <= 3.5:
            L = linhas[-1]
            L["ix"].add(i); L["x0"] = min(L["x0"], bbox[0])
            L["x1"] = max(L["x1"], bbox[2]); L["shp"] += npts; L["n"] += 1
        else:
            linhas.append({"y": bbox[1], "ix": {i}, "x0": bbox[0],
                           "x1": bbox[2], "shp": npts, "n": 1})
    out = []
    for L in linhas:
        if L["n"] < 3:
            continue
        key = ("PL", round(L["y"] / 4), round(L["x0"] / 4), round(L["x1"] / 4),
               L["n"], L["shp"] % 99991)
        out.append((key, L["ix"], (L["x0"], L["y"], L["x1"])))
    return out


def _zona_ok(bbox, H):
    """bbox totalmente na faixa de topo ou de base da página?"""
    return bbox[1] >= H * (1 - ZONA_TOPO) or bbox[3] <= H * ZONA_BASE


def _grupo(page):
    box = page.mediabox
    return (round(float(box[2]) - float(box[0])), round(float(box[3]) - float(box[1])))


def _eh_regua(bbox, W, H):
    """Linha horizontal larga e fina (separador de cabeçalho/rodapé)."""
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    if w < 0.45 * W or h > 3.5:
        return None
    if bbox[1] >= H * 0.72:
        return "topo"
    if bbox[3] <= H * 0.18:
        return "base"
    return None


# Limite de páginas abaixo do qual a detecção por repetição não é confiável e
# passamos a usar também a régua separadora da PRÓPRIA página como corte.
MAX_PAG_CURTO = 4
# Faixa fixa (fração da altura) usada como corte de topo/base quando NÃO há
# régua separadora na página curta (ex.: documentos escaneados sem linha).
FAIXA_TOPO_FRAC = 0.072   # ~6% superior (logo/órgão)
FAIXA_BASE_FRAC = 0.075   # ~7,5% inferior (endereço/rodapé)


def _corte_regua_pagina(els, W, H):
    """Detecta cortes de cabeçalho/rodapé pela régua separadora horizontal
    DA PRÓPRIA PÁGINA (sem exigir repetição entre páginas). Usado em
    documentos curtos. Retorna (cut_topo, cut_base) — qualquer um pode ser
    None. cut_topo é a régua de topo mais baixa (limite inferior do
    cabeçalho); cut_base é a régua de base mais alta (limite superior do
    rodapé). Só considera cortes que deixem o miolo da página intacto.

    No layout do MPSC a régua costuma ficar ENTRE o logotipo e a linha do
    órgão ("11ª Promotoria...", "Centro de Apoio..."), de modo que essa linha
    fica logo ABAIXO da régua e ainda é cabeçalho. Por isso, quando há uma ou
    mais linhas de texto coladas logo abaixo da régua (gap pequeno), o corte
    é estendido para baixo até englobá-las."""
    reg_topo, reg_base = [], []
    for kind, key, bbox, instrs, rot in els:
        if kind == "P" and bbox and not rot:
            lado = _eh_regua(bbox, W, H)
            if lado == "topo":
                reg_topo.append(bbox[1])
            elif lado == "base":
                reg_base.append(bbox[3])
    cut_topo = min(reg_topo) if reg_topo else None
    cut_base = max(reg_base) if reg_base else None
    # Salvaguardas: a régua de topo não pode invadir o corpo (abaixo de 72% da
    # altura) nem a de base subir demais (acima de 18%).
    if cut_topo is not None and cut_topo < H * 0.72:
        cut_topo = None
    if cut_base is not None and cut_base > H * 0.18:
        cut_base = None

    # Estende o corte de topo para baixo enquanto houver linhas de cabeçalho
    # coladas (a linha do órgão logo abaixo da régua). Para no primeiro gap
    # grande (início do corpo do documento).
    if cut_topo is not None:
        clusters = sorted((c for c in _clusters_topo(els, H) if c[2][1] < cut_topo),
                          key=lambda c: -c[2][1])
        ref = cut_topo
        for _key, _ixs, span in clusters:
            y = span[1]
            if ref - y <= 22:        # colada à régua/linha anterior do cabeçalho
                cut_topo = y - 4
                ref = y
            else:
                break

    return cut_topo, cut_base


def _faixa_assinatura_vetorial(els, W, H):
    """Detecta a coluna da assinatura digital quando ela vem desenhada como
    vetor (caminhos), e não como texto rotacionado (já tratado por 'rot').
    Retorna (x0, x1) da faixa a remover, ou None.

    A assinatura é uma coluna vertical estreita, alta e MUITO densa junto a
    uma das margens. O desafio é separá-la do texto de corpo justificado,
    cujas últimas letras de cada linha também caem perto da margem. A
    distinção é a DENSIDADE: varremos colunas finas e mantemos apenas as de
    densidade alta (muitos glifos por extensão vertical) e grande cobertura;
    o corpo, mesmo ocupando toda a altura, tem poucos glifos por coluna."""
    LARG_COL = 4.0
    DENS_MIN = 12.0          # glifos por 100 pt de altura (assinatura ~20; corpo ~5)
    COB_MIN = 0.55           # coluna cobre >= 55% da altura da página
    cols = defaultdict(list)
    for kind, key, bbox, instrs, rot in els:
        if kind == "P" and bbox and not rot:
            xc = (bbox[0] + bbox[2]) / 2
            if xc >= W * 0.78 or xc <= W * 0.22:   # só nas margens
                cols[int(xc // LARG_COL)].append((bbox[1] + bbox[3]) / 2)
    densas = []
    for b, ys in cols.items():
        if len(ys) < 25:
            continue
        span = max(ys) - min(ys)
        if span < H * COB_MIN:
            continue
        if len(ys) / span * 100.0 >= DENS_MIN:
            densas.append(b * LARG_COL)
    if not densas:
        return None
    # une colunas densas adjacentes (a assinatura pode ocupar 1-2 colunas finas)
    return (min(densas) - 6, max(densas) + LARG_COL + 6)


def analisar(pdf):
    """Pass A (1 leitura por página). Vide reescrever() para o uso."""
    contagem = defaultdict(set)
    zonas = {}
    tam_grupo = defaultdict(int)
    reguas = defaultdict(lambda: defaultdict(list))
    for i, page in enumerate(pdf.pages):
        g = _grupo(page)
        tam_grupo[g] += 1
        W, H = g
        els = _elementos(page)
        if els is None:
            continue
        for lk, _ix, _span in _clusters_topo(els, H):
            contagem[(g, lk)].add(i)
            zonas[(g, lk)] = (0, H * (1 - ZONA_TOPO), W, H)
        for kind, key, bbox, instrs, rot in els:
            if kind is None or rot:
                continue
            if kind in ("T", "I", "II"):
                if _zona_ok(bbox, H):
                    contagem[(g, key)].add(i)
                    zonas[(g, key)] = bbox
            elif kind == "P":
                lado = _eh_regua(bbox, W, H)
                if lado:
                    y = bbox[1] if lado == "topo" else bbox[3]
                    reguas[g][(lado, round(y / 6))].append((i, y))
                if bbox[3] <= H * 0.10:
                    contagem[(g, key)].add(i)
                    zonas[(g, key)] = bbox

    boiler, boiler_base_P = set(), set()
    ys_boiler = defaultdict(list)
    for (g, key), pags in contagem.items():
        thr = max(3, math.ceil(tam_grupo[g] * FRACAO_REPETICAO))
        if len(pags) < thr:
            continue
        if key[0] == "P":
            boiler_base_P.add((g, key))
            ys_boiler[g].append(zonas[(g, key)][1])
        else:
            boiler.add((g, key))  # 'T', 'I', 'II' e linhas 'PL'
    faixas_base = {}
    for g, ys in ys_boiler.items():
        ys = sorted(ys)
        ints = []
        for y in ys:
            if ints and y - ints[-1][1] <= 3:
                ints[-1][1] = y
                ints[-1][2] += 1
            else:
                ints.append([y, y, 1])
        faixas_base[g] = [(lo - 2.0, hi + 1.2) for lo, hi, n in ints if n >= 5]

    cortes = {}
    for g, d in reguas.items():
        thr = max(3, math.ceil(tam_grupo[g] * FRACAO_REPETICAO))
        for (lado, fy), occ in d.items():
            if len({p for p, _ in occ}) < thr:
                continue
            for p, y in occ:
                ct, cb = cortes.get(p, (None, None))
                if lado == "topo":
                    ct = y if ct is None else min(ct, y)
                else:
                    cb = y if cb is None else max(cb, y)
                cortes[p] = (ct, cb)

    # --- Fallback para DOCUMENTOS CURTOS -------------------------------------
    # A detecção por repetição precisa de >= 3 páginas; em despachos, portarias,
    # pareceres etc. (1-2 páginas) o cabeçalho/rodapé escapava. Nesses casos,
    # usamos a régua separadora da própria página como corte; se não houver
    # régua, recorremos a faixas fixas no topo e na base.
    n_total_pag = len(pdf.pages)
    if n_total_pag <= MAX_PAG_CURTO:
        for i, page in enumerate(pdf.pages):
            W, H = _grupo(page)
            els = _elementos(page)
            if els is None:
                continue
            ct, cb = cortes.get(i, (None, None))
            rct, rcb = _corte_regua_pagina(els, W, H)
            # combina com o que já houver (mantém o corte mais conservador:
            # topo mais baixo, base mais alta)
            if rct is not None:
                ct = rct if ct is None else min(ct, rct)
            elif ct is None:
                ct = H * (1 - FAIXA_TOPO_FRAC)   # sem régua: faixa fixa de topo
            if rcb is not None:
                cb = rcb if cb is None else max(cb, rcb)
            elif cb is None:
                cb = H * FAIXA_BASE_FRAC          # sem régua: faixa fixa de base
            cortes[i] = (ct, cb)

    return boiler, boiler_base_P, cortes, faixas_base


def _tiras_corpo(els, W, H):
    """Índices das imagens que formam o CORPO ESCANEADO fatiado em tiras.

    Scans do SIG frequentemente vêm desenhados como 2-3 TIRAS horizontais de
    imagem: cada uma cobre ~100% da largura, mas só 33-47% da altura — abaixo
    de IMG_PAGINA_FRAC, então a proteção de "imagem de página inteira" (que
    exige >= 80% da largura E da altura POR IMAGEM) não as alcança, e os
    cortes de topo/base apagariam o documento inteiro (página em branco ->
    OCR de lixo). Regra: se a UNIÃO dos intervalos verticais das imagens
    LARGAS (>= IMG_PAGINA_FRAC da largura) cobre >= IMG_PAGINA_FRAC da altura
    da página, essas imagens são o corpo escaneado e NUNCA são removidas
    (preservação conservadora, CLAUDE.md §5). Banners/logos decorativos rasos
    não são afetados: a união deles fica muito abaixo do limiar."""
    tiras = [(i, bbox) for i, (kind, _key, bbox, _instrs, rot) in enumerate(els)
             if kind in ("I", "II") and bbox and not rot
             and (bbox[2] - bbox[0]) >= W * IMG_PAGINA_FRAC]
    if not tiras:
        return set()
    cobertura = 0.0
    lo = hi = None
    for y0, y1 in sorted((b[1], b[3]) for _i, b in tiras):
        if lo is None:
            lo, hi = y0, y1
        elif y0 <= hi + 2:          # tiras emendadas (tolerância de 2 pt)
            hi = max(hi, y1)
        else:
            cobertura += hi - lo
            lo, hi = y0, y1
    cobertura += hi - lo
    if cobertura >= H * IMG_PAGINA_FRAC:
        return {i for i, _b in tiras}
    return set()


def reescrever(pdf, page, idx, boiler, boiler_base_P, cortes, faixas_base, sem_cabecalho):
    g = _grupo(page)
    W, H = g
    cut_topo, cut_base = cortes.get(idx, (None, None))
    els = _elementos(page)
    if els is None:
        return False

    # Corpo escaneado fatiado em tiras: protegido ANTES de qualquer corte.
    tiras_corpo = _tiras_corpo(els, W, H)

    drop_ix = set()
    spans_rem = []
    if sem_cabecalho:
        for lk, ixs, span in _clusters_topo(els, H):
            if (g, lk) in boiler:
                drop_ix.update(ixs)
                spans_rem.append(span)

    # Faixa vertical da assinatura digital quando ela vem vetorizada (caminhos).
    faixa_assin = _faixa_assinatura_vetorial(els, W, H) if sem_cabecalho else None

    novas = []
    alterado = False
    for i, (kind, key, bbox, instrs, rot) in enumerate(els):
        drop = False
        if i in drop_ix:
            drop = True
        elif rot:
            drop = True
        elif faixa_assin and kind == "P" and bbox and \
                bbox[0] >= faixa_assin[0] and bbox[2] <= faixa_assin[1]:
            drop = True  # glifo da assinatura digital vertical vetorizada
        elif kind == "T":
            if sem_cabecalho and bbox:
                if (g, key) in boiler:
                    drop = True
                elif cut_topo is not None and bbox[1] >= cut_topo - 1:
                    drop = True
                elif cut_base is not None and bbox[3] <= cut_base + 1:
                    drop = True
                elif (bbox[1] >= H - FAIXA_TOPO_TXT or bbox[3] <= FAIXA_BASE_TXT
                      or (bbox[1] >= H - CANTO_DIR_Y and bbox[0] >= CANTO_DIR_X)):
                    drop = True
        elif kind == "P" and bbox and spans_rem and bbox[1] >= H * (1 - ZONA_TOPO) and \
                any(x0 - 12 <= bbox[0] and bbox[2] <= x1 + 12 and abs(bbox[1] - y) <= 7
                    for x0, y, x1 in spans_rem):
            drop = True  # glifo órfão colado a uma linha removida (ex.: cedilha)
        elif kind in ("P", "I", "II"):
            tracado = kind == "P" and key and str(key[-1]) in ("S", "s", "B", "B*", "b", "b*")
            # Imagem que cobre QUASE A PÁGINA INTEIRA (>=80% da largura E da
            # altura) é o CORPO do documento (página escaneada/desenhada), não
            # cabeçalho/rodapé. Nunca a removemos pelos cortes de topo/base —
            # do contrário a página inteira ficaria em branco e o OCR não teria
            # o que ler. (Antes, o topo de uma imagem de página inteira sempre
            # "cruzava" o corte de topo e a imagem era apagada.)
            img_pagina_inteira = (
                kind in ("I", "II") and bbox
                and (bbox[2] - bbox[0]) >= W * IMG_PAGINA_FRAC
                and (bbox[3] - bbox[1]) >= H * IMG_PAGINA_FRAC)
            # Também protege o corpo escaneado FATIADO em tiras (vide
            # _tiras_corpo): nenhuma tira passa no teste acima sozinha, mas
            # juntas elas são a própria página.
            if img_pagina_inteira or i in tiras_corpo:
                drop = False  # protege o corpo escaneado
            elif bbox and tracado and bbox[2] <= CANTO_X and bbox[1] >= H - CANTO_Y:
                drop = True  # moldura do carimbo CÓPIA (contorno tracejado)
            elif sem_cabecalho and bbox:
                if kind in ("I", "II") and (g, key) in boiler:
                    drop = True
                elif kind == "P" and (g, key) in boiler_base_P:
                    drop = True
                elif cut_topo is not None and bbox[3] >= cut_topo - 2:
                    drop = True  # acima (ou cruzando) o corte de topo
                elif cut_base is not None and bbox[1] <= cut_base + 2:
                    drop = True  # abaixo (ou cruzando) o corte de base
                elif kind == "P" and bbox[3] <= H * 0.12 and \
                        any(lo <= bbox[1] <= hi for lo, hi in faixas_base.get(g, ())):
                    drop = True  # varredura do rodapé vetorizado
        if drop:
            alterado = True
        else:
            novas.extend(instrs)

    if alterado:
        page.Contents = pdf.make_stream(unparse_content_stream(novas))
    return alterado


# ----------------------------- TXT / OCR ------------------------------------

def _tessdata_embutido():
    """Pasta de tessdata EMBUTIDA no aplicativo, se existir (ou None).

    É o por.traineddata do tessdata_BEST que acompanha o programa:
      - app congelado (PyInstaller): <sys._MEIPASS>/tesseract/tessdata;
      - ambiente de desenvolvimento: <pasta do script>/assets/tessdata_best.
    Tem PRIORIDADE sobre qualquer instalação do sistema: o instalador típico
    do Tesseract traz o modelo FAST (quantizado, ~2 MB), de precisão menor;
    o embutido garante o stack de melhor qualidade (tessdata_best, CLAUDE.md
    §4) e a operação 100% offline."""
    bases = []
    if hasattr(sys, "_MEIPASS"):
        bases.append(Path(sys._MEIPASS) / "tesseract" / "tessdata")
    try:
        bases.append(Path(__file__).resolve().parent / "assets" / "tessdata_best")
    except Exception:
        pass
    for b in bases:
        try:
            if (b / "por.traineddata").is_file():
                return b
        except Exception:
            continue
    return None


def _localizar_tessdata_por():
    """Procura um 'por.traineddata' ja existente no PC (sem baixar nada).

    Cobre o caso comum de o usuario ter o portugues numa pasta 'tessdata'
    AVULSA (ex.: baixada junto de outra ferramenta como o IPED) que nao e a
    pasta de idiomas usada pela instalacao do Tesseract. Retorna o caminho da
    PASTA 'tessdata' que contem o 'por.traineddata', ou None."""
    import os

    candidatos = []

    # 1) Pasta apontada pela variavel de ambiente do proprio Tesseract.
    for var in ("TESSDATA_PREFIX",):
        v = os.environ.get(var)
        if v:
            candidatos.append(Path(v))
            candidatos.append(Path(v) / "tessdata")

    # 2) Pasta 'tessdata' ao lado do tesseract.exe (instalacao padrao).
    try:
        import pytesseract
        exe = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
        if exe and os.path.isfile(exe):
            candidatos.append(Path(exe).parent / "tessdata")
    except Exception:
        pass

    # 3) Pasta do proprio script / cache do limpa_pdf_mpsc.
    candidatos.append(Path(os.path.expanduser("~")) / ".limpa_pdf_mpsc" / "tessdata")
    try:
        candidatos.append(Path(__file__).resolve().parent / "tessdata")
    except Exception:
        pass

    # 4) Instalacoes comuns do Tesseract no Windows.
    if os.name == "nt":
        for base in (
            os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Tesseract-OCR"),
            os.path.expandvars(r"%LocalAppData%\Programs\Tesseract-OCR"),
            os.path.expandvars(r"%LocalAppData%\Tesseract-OCR"),
        ):
            candidatos.append(Path(base) / "tessdata")

    # Verifica os candidatos diretos primeiro (rapido).
    for c in candidatos:
        try:
            if (c / "por.traineddata").is_file():
                return c
        except Exception:
            continue

    # 5) Ultimo recurso: varredura rasa de pastas 'tessdata' avulsas em locais
    #    tipicos de download (ex.: a pasta do IPED dos prints do usuario).
    if os.name == "nt":
        raizes = [
            Path(os.path.expanduser("~")) / "Downloads",
            Path(os.path.expanduser("~")) / "Desktop",
            Path(os.path.expandvars(r"%OneDrive%")) if os.environ.get("OneDrive") else None,
        ]
        for raiz in raizes:
            if not raiz or not raiz.is_dir():
                continue
            try:
                # procura ate uma profundidade razoavel por por.traineddata
                for arq in raiz.rglob("tessdata/por.traineddata"):
                    if arq.is_file():
                        return arq.parent
            except Exception:
                continue
    return None


def _preparar_ocr():
    """Localiza o Tesseract (mesmo fora do PATH) e garante o idioma portugues.

    Ordem de prioridade:
      0. tessdata_best EMBUTIDO no aplicativo (bundle congelado ou assets/)
         -> melhor qualidade e 100% offline;
      1. portugues ja visivel para o Tesseract (config padrao);
      2. 'por.traineddata' encontrado em alguma pasta conhecida do PC
         (inclui pastas avulsas como a do IPED) -> usa --tessdata-dir, SEM
         baixar nada (funciona offline);
      3. so entao tenta BAIXAR o pacote.
    Retorna (lang, config) ou (None, None) se OCR indisponivel."""
    import os
    import shutil

    try:
        import pytesseract
    except Exception as e:
        print(f"   [aviso] OCR indisponivel (pytesseract: {e}).")
        return None, None

    exe = None
    # Tesseract EMBUTIDO no bundle congelado (PyInstaller): prioridade sobre
    # o PATH e as instalacoes do sistema. E o que garante OCR em maquinas SEM
    # Tesseract instalado (operacao 100% offline) e evita que um exe do
    # sistema, de versao/idiomas diferentes, sobrescreva o do pacote.
    if hasattr(sys, "_MEIPASS"):
        cand = Path(sys._MEIPASS) / "tesseract" / "tesseract.exe"
        if cand.is_file():
            exe = str(cand)
            pytesseract.pytesseract.tesseract_cmd = exe
    if not exe:
        exe = shutil.which("tesseract")
    if not exe and os.name == "nt":
        candidatos = [
            os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LocalAppData%\Tesseract-OCR\tesseract.exe"),
        ]
        exe = next((c for c in candidatos if os.path.isfile(c)), None)
        if exe:
            pytesseract.pytesseract.tesseract_cmd = exe
    if not exe:
        print("   [aviso] Programa Tesseract nao encontrado. Instale-o (veja o"
              " LEIA-ME) ou rode sem --ocr.")
        return None, None

    # (0) tessdata embutido no aplicativo (modelo BEST): prioridade maxima.
    # A instalacao comum do Tesseract traz o modelo FAST; se o programa
    # carrega o proprio tessdata_best, e ELE que garante a qualidade do OCR.
    # Apontado via TESSDATA_PREFIX, e nao '--tessdata-dir "..."': o pytesseract
    # divide o config com shlex NAO-posix no Windows, e as aspas de um caminho
    # com espacos (ex.: "Limpa PDF - Code") chegariam literais ao Tesseract.
    pasta_best = _tessdata_embutido()
    if pasta_best is not None:
        os.environ["TESSDATA_PREFIX"] = str(pasta_best)
        print(f"   OCR: usando o modelo portugues embutido (tessdata_best)"
              f" em {pasta_best}")
        return "por", ""

    # (1) portugues ja disponivel na configuracao padrao do Tesseract?
    try:
        langs = set(pytesseract.get_languages(config=""))
    except Exception:
        langs = set()
    if "por" in langs:
        return "por", ""

    # (2) procurar um por.traineddata ja presente no PC (offline, sem baixar).
    pasta_por = _localizar_tessdata_por()
    if pasta_por is not None:
        cfg = f'--tessdata-dir "{pasta_por}"'
        try:
            if "por" in set(pytesseract.get_languages(config=cfg)):
                print(f"   OCR: usando portugues encontrado em {pasta_por}")
                return "por", cfg
        except Exception:
            pass
        # mesmo que get_languages falhe com o dir custom, o arquivo existe;
        # confiamos nele (o Tesseract o lera via --tessdata-dir).
        print(f"   OCR: usando portugues encontrado em {pasta_por}")
        return "por", cfg

    # (3) portugues ausente em todo lugar: tentar baixar o pacote.
    # Usamos o tessdata_BEST (modelo de maior precisao), e nao o tessdata_fast
    # (modelo quantizado/comprimido). Para documentos juridicos, a diferenca de
    # precisao compensa o leve aumento de tamanho do arquivo e de tempo de OCR.
    destino = Path(os.path.expanduser("~")) / ".limpa_pdf_mpsc" / "tessdata"
    arq = destino / "por.traineddata"
    if not arq.is_file():
        import urllib.request
        destino.mkdir(parents=True, exist_ok=True)
        print("   Baixando idioma portugues do OCR (1a vez, modelo de alta"
              " precisao, ~30 MB)...")
        urls = [
            "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/por.traineddata",
            "https://github.com/tesseract-ocr/tessdata_best/raw/main/por.traineddata",
        ]
        ok = False
        for url in urls:
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (limpa_pdf_mpsc)"})
                with urllib.request.urlopen(req, timeout=60) as r, open(arq, "wb") as f:
                    f.write(r.read())
                ok = arq.stat().st_size > 1_000_000
                if ok:
                    break
            except Exception:
                continue
        if not ok:
            if arq.exists():
                arq.unlink()
            print("   [aviso] Nao consegui baixar o portugues; usando ingles"
                  " (acentos podem sair errados). Se voce ja tem um"
                  " por.traineddata, copie-o para " + str(destino))
            return ("eng", "") if "eng" in langs or langs == set() else (sorted(langs)[0], "")
    cfg = f'--tessdata-dir "{destino}"'
    try:
        if "por" in set(pytesseract.get_languages(config=cfg)):
            return "por", cfg
    except Exception:
        pass
    print("   [aviso] Pacote de portugues nao pode ser usado; usando ingles.")
    return "eng", ""


# Limiar de área (fração da página) para considerar uma imagem EMBUTIDA
# relevante. Acima de IMG_PAGINA_FRAC tratamos como "página-imagem" inteira
# (página escaneada/desenhada), que o OCR já cobre e NÃO gera aviso.
IMG_EMBUTIDA_FRAC = 0.04   # >= 4% da página = imagem relevante a sinalizar
IMG_PAGINA_FRAC = 0.80     # >= 80% da página = a própria página é imagem


def _detectar_tabelas_imagens(pdf_path: Path):
    """Detecta, página a página, a presença de TABELAS e de IMAGENS EMBUTIDAS
    relevantes, para gerar avisos no .txt.

    Objetivo: rede de segurança. Quando uma página tem texto (extraído
    normalmente) mas também traz uma TABELA ou uma IMAGEM embutida (uma foto,
    print, documento anexado — possível prova), o conteúdo visual não vira
    texto e poderia passar despercebido na leitura do .txt. O aviso chama a
    atenção do usuário (ou da IA) para conferir aquela página no original.

    Critérios:
      - Tabela: grade detectada pelo pdfplumber (linhas/bordas formando
        células). Robusto e independente de heurística de texto.
      - Imagem embutida: imagem cuja área seja >= IMG_EMBUTIDA_FRAC da página
        e < IMG_PAGINA_FRAC (acima disso é a própria página escaneada, que o
        OCR cobre e não deve gerar aviso redundante).

    Retorna dict {indice_pagina(0-based): {"tabela": bool, "imagem": bool}}
    contendo APENAS páginas com algo a sinalizar. Em caso de falha (pdfplumber
    ausente etc.), retorna {} silenciosamente — o aviso é um extra, nunca deve
    quebrar a geração do .txt."""
    try:
        import pdfplumber
    except Exception:
        return {}

    avisos = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, p in enumerate(pdf.pages):
                area_pg = (p.width or 1) * (p.height or 1)

                tem_tabela = False
                try:
                    tem_tabela = len(p.find_tables()) > 0
                except Exception:
                    tem_tabela = False

                tem_imagem = False
                try:
                    for im in (p.images or []):
                        w = abs(float(im.get("x1", 0)) - float(im.get("x0", 0)))
                        h = abs(float(im.get("bottom", 0)) - float(im.get("top", 0)))
                        frac = (w * h) / area_pg if area_pg else 0.0
                        if IMG_EMBUTIDA_FRAC <= frac < IMG_PAGINA_FRAC:
                            tem_imagem = True
                            break
                except Exception:
                    tem_imagem = False

                if tem_tabela or tem_imagem:
                    avisos[i] = {"tabela": tem_tabela, "imagem": tem_imagem}
    except Exception:
        return {}
    return avisos


def _texto_aviso(info):
    """Monta o texto do aviso para uma página, a partir do dict {tabela, imagem}."""
    if info.get("tabela") and info.get("imagem"):
        alvo = "tabela e imagem"
    elif info.get("tabela"):
        alvo = "tabela"
    else:
        alvo = "imagem"
    return (f">> AVISO: esta pagina contem {alvo} - revisar no PDF original "
            f"(conteudo visual pode nao ter sido capturado no texto).")


def exportar_txt(pdf_path: Path, txt_path: Path, avisos=None, offset: int = 1):
    """Extrai o texto do PDF (com pypdfium2; pdfplumber é reserva).

    'offset' é o número (1-based) da primeira página desta parte no documento
    inteiro, para que o cabeçalho "===== Pagina N =====" seja CONTÍNUO entre as
    partes (casando com o número carimbado no PDF). 'avisos' é indexado por
    página 0-based DENTRO desta parte.

    Se 'avisos' (dict de _detectar_tabelas_imagens) for fornecido, insere um
    RESUMO no topo do .txt e um aviso inline no cabeçalho de cada página
    afetada, para sinalizar tabelas/imagens que merecem conferência no
    original.

    Páginas cujo texto extraído seja vazio OU lixo (fonte sem /ToUnicode, não
    corrigida por falta de --ocr) recebem o aviso de página sem texto, em vez
    de despejar o lixo no .txt."""
    avisos = avisos or {}
    motor = None
    try:
        import pypdfium2 as pdfium
        motor = "pdfium"
    except Exception:
        try:
            import pdfplumber  # noqa: F401
            motor = "plumber"
        except Exception as e:
            print(f"   [aviso] .txt nao gerado ({e}). Rode no terminal:"
                  "  python -m pip install pypdfium2")
            return
    aviso_sem_texto = ("[pagina sem texto aproveitavel - use --ocr"
                       " (com o Tesseract instalado) para extrair]")
    saida = []
    if motor == "pdfium":
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(pdf_path))
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            texto = (tp.get_text_range() or "").strip()
            tp.close()
            if not _texto_e_aproveitavel(texto):
                texto = aviso_sem_texto
            cab = f"===== Pagina {offset + i} ====="
            if i in avisos:
                cab += "\n" + _texto_aviso(avisos[i])
            saida.append(f"{cab}\n{texto}")
        doc.close()
    else:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pl:
            for i, p in enumerate(pl.pages):
                texto = (p.extract_text() or "").strip()
                if not _texto_e_aproveitavel(texto):
                    texto = aviso_sem_texto
                cab = f"===== Pagina {offset + i} ====="
                if i in avisos:
                    cab += "\n" + _texto_aviso(avisos[i])
                saida.append(f"{cab}\n{texto}")
    corpo = "\n\n".join(saida)
    if avisos:
        pags = sorted(offset + k for k in avisos)
        lista = ", ".join(str(n) for n in pags)
        resumo = (
            "############################################################\n"
            "# ATENCAO - REDE DE SEGURANCA (revisao no original)\n"
            f"# Paginas com tabela/imagem a conferir: {lista}\n"
            "# O texto abaixo pode NAO conter tabelas/imagens dessas\n"
            "# paginas. Verifique-as no PDF original para nao perder\n"
            "# informacao ou prova relevante.\n"
            "############################################################"
        )
        corpo = resumo + "\n\n" + corpo
    txt_path.write_text(corpo, encoding="utf-8")


def _normalizar_ocr(texto: str) -> str:
    """Corrige trocas SISTEMÁTICAS e seguras do OCR do Tesseract no acervo do
    SIG, sem inventar correções de palavra.

    O caso mais comum é o "a"/"o" minúsculos serem reconhecidos como os
    ordinais "ª"/"º" (U+00AA / U+00BA) em fontes finas. Substituímos SOMENTE
    quando o ordinal aparece COLADO a uma letra (ex.: "ª" em "ªtuªl"), nunca
    quando está junto a dígito (ex.: "1ª", "2º" são legítimos e preservados).
    É uma rede de segurança barata; o ganho real vem do pré-processamento e do
    modelo best. Mantém acentos e o restante do texto intactos."""
    if not texto:
        return texto
    # ordinal feminino colado a letra -> "a"
    texto = re.sub(r"(?<=[A-Za-zÀ-ÿ])ª", "a", texto)
    texto = re.sub(r"ª(?=[A-Za-zÀ-ÿ])", "a", texto)
    # ordinal masculino colado a letra -> "o"
    texto = re.sub(r"(?<=[A-Za-zÀ-ÿ])º", "o", texto)
    texto = re.sub(r"º(?=[A-Za-zÀ-ÿ])", "o", texto)
    return texto


def _escapa_pdf(b: bytes) -> bytes:
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


# Larguras dos glifos da Helvetica (AFM padrão, em milésimos de "em"), usadas
# para calcular a escala horizontal (Tz) de cada palavra do OCR de modo que ela
# cubra EXATAMENTE a largura medida na imagem. Sem isto o texto fica largo/
# estreito demais e não casa com a imagem.
_HELV_W = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667,
    "'": 191, '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333,
    '.': 278, '/': 278, '0': 556, '1': 556, '2': 556, '3': 556, '4': 556,
    '5': 556, '6': 556, '7': 556, '8': 556, '9': 556, ':': 278, ';': 278,
    '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015, 'A': 667, 'B': 667,
    'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778, 'H': 722, 'I': 278,
    'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778, 'P': 667,
    'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
    'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469,
    '_': 556, '`': 333, 'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556,
    'f': 278, 'g': 556, 'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222,
    'm': 833, 'n': 556, 'o': 556, 'p': 556, 'q': 556, 'r': 333, 's': 500,
    't': 278, 'u': 556, 'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 500,
    '{': 334, '|': 260, '}': 334, '~': 584,
    # acentuados comuns no português (largura ~ da letra base)
    'á': 556, 'à': 556, 'ã': 556, 'â': 556, 'ä': 556, 'é': 556, 'ê': 556,
    'è': 556, 'í': 278, 'ì': 278, 'î': 278, 'ó': 556, 'ô': 556, 'õ': 556,
    'ò': 556, 'ö': 556, 'ú': 556, 'ù': 556, 'û': 556, 'ü': 556, 'ç': 500,
    'ñ': 556, 'Á': 667, 'À': 667, 'Ã': 667, 'Â': 667, 'É': 667, 'Ê': 667,
    'Í': 278, 'Ó': 778, 'Ô': 778, 'Õ': 778, 'Ú': 722, 'Ç': 722,
}


def _larg_helvetica(s: str) -> float:
    """Largura natural do texto na Helvetica, em unidades de 'em' (font size = 1)."""
    return sum(_HELV_W.get(ch, 556) for ch in s) / 1000.0


def _inverter_matriz(m):
    """Inversa de uma matriz afim do PDF (a b c d e f). None se singular."""
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-9:
        return None
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_))


def _ctm_residual(page):
    """Calcula o CTM acumulado que sobra ao FINAL do content stream da página.

    Muitos PDFs do SIG iniciam o stream com um 'cm' (ex.: 0.75 0 0 -0.75 0 H)
    SEM um 'q' anterior, de modo que essa transformação fica "vazada" no estado
    gráfico. Como a camada de OCR é anexada ao fim do stream, ela herdaria esse
    CTM e o texto sairia deslocado/condensado. Medindo o residual conseguimos
    neutralizá-lo aplicando a matriz inversa antes de desenhar o texto."""
    try:
        instrs = parse_content_stream(page)
    except Exception:
        return I
    ctm = I
    pilha = []
    for operands, op in instrs:
        o = str(op)
        if o == "q":
            pilha.append(ctm)
        elif o == "Q":
            ctm = pilha.pop() if pilha else I
        elif o == "cm" and len(operands) == 6:
            try:
                ctm = mul(tuple(float(v) for v in operands), ctm)
            except Exception:
                pass
    return ctm


# --------------------------- parâmetros de OCR ------------------------------
# Resolução de renderização para o OCR. 400 dpi (antes 300) dá mais pixels por
# glifo e reduz o colapso de letras finas e cinzas dos PDFs do SIG (o típico
# "a" virando "ª", "denúncia" virando "Henúncia"). Custo: render e OCR ~1,8x
# mais lentos e mais memória. Ajuste aqui se precisar do compromisso inverso.
OCR_DPI = 400
# Maior lado (em pixels) permitido na imagem renderizada para OCR. Páginas com
# mediabox gigante (ex.: scans de 2290x3286 pt) gerariam imagens enormes a 400
# dpi (>12000 px), estourando memória e tempo sem ganho de precisão. Quando o
# render passaria disso, reduzimos a escala para caber neste teto.
OCR_MAX_LADO_PX = 5000
# Limiar de binarização (0-255) aplicado após o aumento de contraste. Pixels
# mais escuros que o limiar viram preto; o resto, branco. Mais ALTO engrossa o
# texto (bom p/ fonte fininha); mais BAIXO preserva detalhe mas mantém ruído.
# Faixa útil típica: 150-175. Só é usado quando OpenCV NÃO está disponível
# (com OpenCV usamos Otsu, que escolhe o limiar sozinho por página).
OCR_LIMIAR_BIN = 160
# Liga/desliga a binarização. Em raros documentos já muito limpos ela pode
# atrapalhar; deixe True para o acervo do SIG (fonte cinza serrilhada).
OCR_BINARIZAR = True

# --- Detecção de camada de texto CORROMPIDA (força OCR) ---------------------
# Alguns PDFs do SIG trazem uma "camada de texto" que NÃO é texto legível: a
# fonte embarcada não tem mapeamento p/ Unicode (sem /ToUnicode), de modo que
# a extração devolve caracteres de controle e da Área de Uso Privado (PUA) —
# lixo. O código antigo via len>=20 e PULAVA o OCR, deixando esse lixo entrar
# no .txt. Agora medimos a "qualidade" do texto extraído: se ele for
# majoritariamente lixo (poucos alfanuméricos, muitos caracteres de controle/
# PUA), tratamos a página como SEM texto e a enviamos ao OCR — substituindo a
# camada podre pela do OCR.
#
# Limiares (calibrados nos exemplos reais do acervo: páginas boas têm
# ~70%+ de alfanuméricos e ~0% de controle; páginas podres, <25% alfanum. e
# 40-75% de controle):
OCR_MIN_FRAC_ALNUM = 0.45   # texto bom tem >= 45% de caracteres alfanuméricos
OCR_MAX_FRAC_LIXO = 0.20    # texto bom tem <= 20% de caracteres de controle/PUA
OCR_MIN_CHARS_AVAL = 20     # só avalia qualidade a partir deste tamanho


def _qualidade_texto(t: str):
    """Mede a fração de caracteres alfanuméricos e a fração de 'lixo'
    (controle/Área de Uso Privado/não-atribuídos) num texto extraído.
    Devolve (frac_alnum, frac_lixo) sobre os caracteres NÃO brancos."""
    import unicodedata
    ns = [c for c in t if not c.isspace()]
    if not ns:
        return 0.0, 0.0
    alnum = 0
    lixo = 0
    for c in ns:
        if c.isalnum():
            alnum += 1
        o = ord(c)
        # caracteres de controle (exceto whitespace, já filtrado) ou
        # categorias Unicode 'Co' (uso privado) e 'Cn' (não atribuído)
        if o < 32 or unicodedata.category(c) in ("Co", "Cn"):
            lixo += 1
    n = len(ns)
    return alnum / n, lixo / n


def _texto_e_aproveitavel(t: str) -> bool:
    """True se o texto extraído da página é texto REAL aproveitável; False se
    está vazio/curto demais OU é majoritariamente lixo (fonte sem ToUnicode).
    Quando False, a página deve ir para o OCR."""
    t = (t or "").strip()
    if len(t) < OCR_MIN_CHARS_AVAL:
        return False
    frac_alnum, frac_lixo = _qualidade_texto(t)
    if frac_lixo > OCR_MAX_FRAC_LIXO:
        return False
    if frac_alnum < OCR_MIN_FRAC_ALNUM:
        return False
    return True


def _remover_camada_texto(pdf, page):
    """Remove TODAS as instruções de texto (blocos BT...ET) do content stream
    da página, preservando o restante (imagens, caminhos). Usado quando a
    camada de texto existente é lixo (fonte sem ToUnicode): apagamos o lixo
    antes de sobrepor a camada de OCR, senão a extração continuaria pegando o
    lixo em vez do texto do OCR. Retorna True se removeu algo."""
    try:
        instrs = list(parse_content_stream(page))
    except Exception:
        return False
    novas = []
    em_bt = False
    removeu = False
    for item in instrs:
        op = item[1]
        if op == Operator("BT"):
            em_bt = True
            removeu = True
            continue
        if op == Operator("ET"):
            em_bt = False
            continue
        if em_bt:
            continue
        novas.append(item)
    if removeu:
        page.Contents = pdf.make_stream(unparse_content_stream(novas))
    return removeu


def _preparar_imagem_ocr(img):
    """Pré-processa a imagem da página ANTES do OCR, para melhorar a leitura de
    fontes finas e acinzentadas (o caso dos PDFs do SIG renderizados).

    Pipeline: tons de cinza -> aumento de contraste -> binarização (preto/
    branco). A binarização é o passo que mais ajuda o "a→ª": ela fecha a
    barriga do "a" que, em cinza-claro, o Tesseract via aberta.

    Usa OpenCV (binarização de Otsu, que escolhe o limiar por página) quando
    disponível; senão, cai para Pillow com limiar fixo (OCR_LIMIAR_BIN). Nunca
    quebra: se algo falhar, devolve a imagem original em tons de cinza."""
    from PIL import Image, ImageOps

    if not OCR_BINARIZAR:
        return img.convert("L")

    # Caminho preferido: OpenCV + Otsu (limiar automático, robusto a variação
    # de qualidade entre páginas/documentos).
    try:
        import cv2
        import numpy as np
        arr = np.array(img.convert("L"))
        # leve suavização para tirar o serrilhado antes de binarizar
        arr = cv2.bilateralFilter(arr, d=5, sigmaColor=40, sigmaSpace=40)
        _, bin_arr = cv2.threshold(
            arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(bin_arr)
    except Exception:
        pass

    # Fallback: Pillow puro (sem dependência extra).
    try:
        g = img.convert("L")
        g = ImageOps.autocontrast(g, cutoff=1)
        lim = OCR_LIMIAR_BIN
        return g.point(lambda p: 0 if p < lim else 255)
    except Exception:
        return img.convert("L")


def embutir_ocr(pdf_path: Path, lang: str, cfg: str) -> int:
    """Acrescenta, nas páginas SEM camada de texto, texto invisível de OCR
    (Text Rendering Mode 3) POR CIMA do conteúdo, palavra a palavra, para
    que o texto fique selecionável e pesquisável em qualquer leitor.

    A camada é desenhada com o CTM herdado do conteúdo neutralizado, em
    coordenadas absolutas de página, com tamanho de fonte e escala horizontal
    ajustados a cada palavra — de modo que o texto invisível coincida com as
    palavras da imagem (a seleção do mouse "casa" com o que se vê).
    Retorna o nº de páginas ocerizadas."""
    import pypdfium2 as pdfium
    import pytesseract

    # Garante o motor neural (LSTM, --oem 1) e a segmentação por bloco uniforme
    # de texto (--psm 6), que dá melhor resultado no corpo dos documentos do
    # SIG. Preserva o que já vier em 'cfg' (ex.: --tessdata-dir).
    cfg_ocr = f"{cfg or ''} --oem 1 --psm 6".strip()

    pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    n_ocr = 0
    try:
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            existente = (tp.get_text_range() or "").strip()
            tp.close()
            # Antes: pulava o OCR sempre que len>=20. Problema: páginas com
            # camada de texto CORROMPIDA (fonte sem /ToUnicode) têm len grande
            # mas o conteúdo é lixo (controle/PUA) — e o lixo ia parar no .txt.
            # Agora só pulamos se o texto for REALMENTE aproveitável.
            if _texto_e_aproveitavel(existente):
                continue
            # Página sem texto OU com camada podre: se havia camada podre,
            # removemo-la antes de sobrepor o OCR (senão a extração continuaria
            # pegando o lixo em vez do texto do OCR).
            if len(existente) >= OCR_MIN_CHARS_AVAL:
                try:
                    if _remover_camada_texto(pdf, page):
                        print(f"   Pag {i + 1}: camada de texto corrompida"
                              " removida; aplicando OCR.", flush=True)
                except Exception as e:
                    print(f"   [aviso] nao removi a camada podre da pag"
                          f" {i + 1}: {e}")
            # Render em OCR_DPI (400): mais pixels por glifo, menos colapso de
            # letras finas. Pré-processa (cinza + contraste + binarização) para
            # destacar o texto cinza serrilhado antes de reconhecer.
            # Cap de segurança: páginas com mediabox gigante (alguns scans do
            # SIG têm 2290x3286 pt) gerariam imagens de >12000 px a 400 dpi,
            # estourando memória/tempo sem ganho. Limitamos o maior lado.
            escala = OCR_DPI / 72.0
            box0 = page.mediabox
            w_pt = float(box0[2]) - float(box0[0])
            h_pt = float(box0[3]) - float(box0[1])
            maior_px = max(w_pt, h_pt) * escala
            if maior_px > OCR_MAX_LADO_PX:
                escala = OCR_MAX_LADO_PX / max(w_pt, h_pt)
            img = doc[i].render(scale=escala).to_pil()
            img_ocr = _preparar_imagem_ocr(img)
            print(f"   OCR pagina {i + 1}...", flush=True)
            dados = pytesseract.image_to_data(
                img_ocr, lang=lang, config=cfg_ocr,
                output_type=pytesseract.Output.DICT)
            box = page.mediabox
            x0 = float(box[0])
            y0 = float(box[1])
            W = float(box[2]) - x0
            H = float(box[3]) - y0
            sx, sy = W / img.width, H / img.height

            # Neutraliza qualquer CTM herdado do conteúdo original (ex.: o
            # 0.75 0 0 -0.75 0 H típico do SIG), para que as coordenadas em
            # pontos de página fiquem absolutas e o texto caia EXATAMENTE sobre
            # a imagem.
            m_inv = _inverter_matriz(_ctm_residual(page)) or I
            linhas = [
                b"q",
                ("%.6f %.6f %.6f %.6f %.4f %.4f cm" % m_inv).encode("latin-1"),
                b"BT", b"3 Tr",
            ]
            n_pal = 0
            n_total = len(dados["text"])
            for j in range(n_total):
                w = (dados["text"][j] or "").strip()
                w = _normalizar_ocr(w)
                try:
                    conf = int(float(dados["conf"][j]))
                except Exception:
                    conf = -1
                if not w or conf < 40:
                    continue
                left = dados["left"][j]
                top = dados["top"][j]
                wpx = dados["width"][j]
                hpx = dados["height"][j]
                # bbox da palavra em pontos de página (Y do PDF cresce p/ cima)
                x = x0 + left * sx
                base_bbox = y0 + H - (top + hpx) * sy   # fundo da bbox da palavra
                larg_pt = max(wpx * sx, 1.0)
                alt_pt = max(hpx * sy, 4.0)
                # A bbox do Tesseract abrange a altura visível da palavra; numa
                # fonte como a Helvetica as maiúsculas ocupam ~72% do corpo, logo
                # o tamanho de fonte ≈ altura_bbox / 0.72.
                fs = max(alt_pt / 0.72, 4.0)
                # A baseline fica ligeiramente acima do fundo da bbox (descender).
                y = base_bbox + alt_pt * 0.18
                # Escala horizontal: faz a palavra cobrir exatamente larg_pt.
                w_natural = _larg_helvetica(w) * fs
                if w_natural < 0.1:
                    w_natural = 0.1
                tz = max(1.0, min(1000.0, larg_pt / w_natural * 100.0))
                pal = _escapa_pdf(w.encode("cp1252", errors="replace"))
                linhas.append(
                    f"{tz:.1f} Tz /FOCR {fs:.2f} Tf "
                    f"1 0 0 1 {x:.2f} {y:.2f} Tm ".encode("latin-1")
                    + b"(" + pal + b") Tj")
                n_pal += 1
            linhas += [b"ET", b"Q"]
            if n_pal == 0:
                continue
            res = page.get("/Resources")
            if res is None:
                res = pikepdf.Dictionary()
                page.Resources = res
            fontes = res.get("/Font")
            if fontes is None:
                fontes = pikepdf.Dictionary()
                res.Font = fontes
            if "/FOCR" not in fontes:
                fontes["/FOCR"] = pdf.make_indirect(pikepdf.Dictionary(
                    Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                    BaseFont=pikepdf.Name.Helvetica,
                    Encoding=pikepdf.Name.WinAnsiEncoding))
            page.contents_add(pdf.make_stream(b"\n".join(linhas)),
                              prepend=False)
            n_ocr += 1
        if n_ocr:
            doc.close()
            doc = None
            pdf.save(pdf_path)
    finally:
        if doc is not None:
            doc.close()
        pdf.close()
    return n_ocr


# --------------------------- PAGINAÇÃO CONTÍNUA -----------------------------

# Parâmetros do carimbo de página (em pontos). Margens medidas a partir da
# borda da página (canto superior direito).
NUM_FONTE_PT = 10.0     # tamanho da fonte do número (Arial/Helvetica 10)
NUM_MARG_DIR = 36.0     # afastamento da borda direita (~0,5 pol)
NUM_MARG_TOPO = 28.0    # afastamento da borda superior (baseline do texto)


def _rotulo_pagina(num: int, total: int) -> str:
    """Texto do carimbo de página. O formato "[Pagina N de TOTAL]" é explícito
    o bastante para a IA reconhecê-lo como referência de localização e citá-lo
    ao responder onde está uma informação; ao mesmo tempo é discreto na página
    impressa. O "de TOTAL" ajuda a IA a validar que está vendo o documento
    inteiro e dá ao usuário a noção de extensão do procedimento."""
    return f"[Pagina {num} de {total}]"


def numerar_paginas(pdf_path: Path, total: int, inicio: int = 1) -> int:
    """Carimba, em CADA página do PDF, um número visível no canto superior
    direito (Helvetica/Arial 10, preto), como camada de texto selecionável e
    pesquisável — legível tanto pelo usuário quanto pela IA.

    A numeração é CONTÍNUA: a página i recebe o número (inicio + i). Esta
    função é chamada sobre o PDF AINDA INTEIRO, antes da divisão em partes, de
    modo que a contagem vai de 1 até 'total' sem reiniciar a cada parte
    (passa-se 'inicio' apenas para robustez/uso futuro; no fluxo normal é 1).

    Reaproveita a técnica da camada de OCR (v2.3): o carimbo é anexado ao fim
    do content stream com o CTM herdado neutralizado (ex.: o 0.75 0 0 -0.75 0 H
    típico do SIG), garantindo que o número caia em coordenadas absolutas de
    página — exatamente no canto superior direito — e não condensado ou
    deslocado. Retorna o nº de páginas numeradas."""
    n_num = 0
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        for i, page in enumerate(pdf.pages):
            num = inicio + i
            rotulo = _rotulo_pagina(num, total)
            box = page.mediabox
            x0 = float(box[0])
            y0 = float(box[1])
            W = float(box[2]) - x0
            H = float(box[3]) - y0
            # Posição: alinhado à direita (recua a largura do texto) e no topo.
            larg = _larg_helvetica(rotulo) * NUM_FONTE_PT
            x = x0 + W - NUM_MARG_DIR - larg
            y = y0 + H - NUM_MARG_TOPO
            # Neutraliza qualquer CTM herdado do conteúdo (vide _ctm_residual),
            # para que x/y sejam coordenadas absolutas de página.
            m_inv = _inverter_matriz(_ctm_residual(page)) or I
            pal = _escapa_pdf(rotulo.encode("cp1252", errors="replace"))
            linhas = [
                b"q",
                ("%.6f %.6f %.6f %.6f %.4f %.4f cm" % m_inv).encode("latin-1"),
                b"BT",
                b"0 g",                                   # cor preta
                ("/FNUM %.2f Tf" % NUM_FONTE_PT).encode("latin-1"),
                ("1 0 0 1 %.2f %.2f Tm" % (x, y)).encode("latin-1"),
                b"(" + pal + b") Tj",
                b"ET",
                b"Q",
            ]
            res = page.get("/Resources")
            if res is None:
                res = pikepdf.Dictionary()
                page.Resources = res
            fontes = res.get("/Font")
            if fontes is None:
                fontes = pikepdf.Dictionary()
                res.Font = fontes
            if "/FNUM" not in fontes:
                fontes["/FNUM"] = pdf.make_indirect(pikepdf.Dictionary(
                    Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                    BaseFont=pikepdf.Name.Helvetica,
                    Encoding=pikepdf.Name.WinAnsiEncoding))
            page.contents_add(pdf.make_stream(b"\n".join(linhas)),
                              prepend=False)
            n_num += 1
        pdf.save(pdf_path)
    return n_num


def dividir_pdf(caminho: Path, max_pag: int):
    """Divide o PDF em partes de até max_pag páginas. Retorna uma lista de
    tuplas (arquivo, offset), onde 'offset' é o número (1-based) da PRIMEIRA
    página daquela parte no documento inteiro — usado para manter a numeração
    contínua no .txt (parte02 começa em max_pag+1, e assim por diante). O
    original é substituído pelas partes."""
    if not max_pag or max_pag <= 0:
        return [(caminho, 1)]
    with pikepdf.open(caminho) as pdf:
        n = len(pdf.pages)
        if n <= max_pag:
            return [(caminho, 1)]
        partes = []
        k, i = 0, 0
        while i < n:
            k += 1
            novo = pikepdf.new()
            for p in pdf.pages[i:i + max_pag]:
                novo.pages.append(p)
            destino = caminho.with_name(f"{caminho.stem}_parte{k:02d}.pdf")
            novo.save(destino, compress_streams=True,
                      object_stream_mode=pikepdf.ObjectStreamMode.generate)
            partes.append((destino, i + 1))   # offset = 1ª página desta parte
            i += max_pag
    caminho.unlink()
    print(f"   Dividido em {len(partes)} partes de ate {max_pag} paginas.")
    return partes


# ------------------------------- CLI ----------------------------------------

def limpa_pdf(origem: Path, destino: Path, sem_cabecalho: bool) -> int:
    n_alt = 0
    with pikepdf.open(origem) as pdf:
        if sem_cabecalho:
            boiler, boiler_base_P, cortes, faixas_base = analisar(pdf)
        else:
            boiler, boiler_base_P, cortes, faixas_base = set(), set(), {}, {}
        for idx, page in enumerate(pdf.pages):
            if reescrever(pdf, page, idx, boiler, boiler_base_P, cortes, faixas_base, sem_cabecalho):
                n_alt += 1
        pdf.save(destino, compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return n_alt


def main():
    ap = argparse.ArgumentParser(description="Limpa PDFs do SIG MPSC (v2)")
    ap.add_argument("entrada", help="Arquivo PDF ou pasta com PDFs")
    ap.add_argument("--saida", help="Pasta de saída (padrão: sufixo _limpo)")
    ap.add_argument("--sem-cabecalho", action="store_true",
                    help="Remove cabeçalho/rodapé (texto, logos e linhas)")
    ap.add_argument("--txt", action="store_true", help="Exporta .txt limpo")
    ap.add_argument("--ocr", action="store_true",
                    help="OCR nas páginas sem camada de texto (requer Tesseract):"
                         " o texto fica selecionável no PDF e entra no .txt")
    ap.add_argument("--max-paginas", type=int, default=MAX_PAGINAS,
                    help=f"divide PDFs maiores que N páginas (padrão {MAX_PAGINAS};"
                         " use 0 para não dividir)")
    ap.add_argument("--sem-avisos-tabela-imagem", action="store_true",
                    help="NÃO insere no .txt os avisos de páginas com"
                         " tabela/imagem (por padrão os avisos são incluídos"
                         " junto com --txt como rede de segurança)")
    ap.add_argument("--sem-numero", action="store_true",
                    help="NÃO carimba o número da página no canto superior"
                         " direito (por padrão a paginação contínua é"
                         " aplicada para facilitar a referência por IA)")
    args = ap.parse_args()

    lang = cfg = None
    if args.ocr:
        lang, cfg = _preparar_ocr()
        if not lang:
            print("[aviso] Prosseguindo SEM OCR.")

    entrada = Path(args.entrada)
    arquivos = sorted(entrada.rglob("*.pdf")) if entrada.is_dir() else [entrada]
    arquivos = [a for a in arquivos if "_limpo" not in a.stem]
    if not arquivos:
        sys.exit("Nenhum PDF encontrado.")
    pasta = Path(args.saida) if args.saida else None
    if pasta:
        # proteção: se passaram "arquivo.pdf\LIMPOS" (arrastar PDF p/ o .bat),
        # usar a pasta do próprio arquivo como base
        if entrada.is_file() and pasta.parent == entrada:
            pasta = entrada.parent / pasta.name
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError, FileNotFoundError):
            pasta = (entrada.parent if entrada.is_file() else entrada) / "LIMPOS"
            pasta.mkdir(parents=True, exist_ok=True)
            print(f"[aviso] pasta de saída inválida; usando {pasta}")

    for arq in arquivos:
        destino = (pasta / arq.name) if pasta else arq.with_name(arq.stem + "_limpo.pdf")
        try:
            n = limpa_pdf(arq, destino, args.sem_cabecalho)
        except Exception as e:
            print(f"[ERRO] {arq.name}: {e}")
            continue
        if lang:
            try:
                n_ocr = embutir_ocr(destino, lang, cfg)
                if n_ocr:
                    print(f"   OCR embutido em {n_ocr} páginas (texto"
                          " selecionável).")
            except Exception as e:
                print(f"   [aviso] OCR falhou: {e}")
        # Paginação CONTÍNUA: carimba os números ANTES de dividir, sobre o PDF
        # inteiro, para que a contagem vá de 1 ao total sem reiniciar a cada
        # parte. O total é o nº de páginas do documento limpo (já com OCR).
        if not args.sem_numero:
            try:
                with pikepdf.open(destino) as _p:
                    total_pag = len(_p.pages)
                numerar_paginas(destino, total_pag, inicio=1)
                print(f"   Paginas numeradas (1 a {total_pag}) no canto"
                      " superior direito.")
            except Exception as e:
                print(f"   [aviso] numeração de páginas falhou: {e}")
        try:
            partes = dividir_pdf(destino, args.max_paginas)
        except Exception as e:
            print(f"   [aviso] não consegui dividir ({e}); arquivo único.")
            partes = [(destino, 1)]
        nomes = []
        for parte, offset in partes:
            nomes.append(parte.name)
            if args.txt:
                txt = parte.with_suffix(".txt")
                avisos = {}
                if not args.sem_avisos_tabela_imagem:
                    try:
                        avisos = _detectar_tabelas_imagens(parte)
                    except Exception as e:
                        print(f"   [aviso] deteccao de tabela/imagem falhou ({e}).")
                        avisos = {}
                try:
                    exportar_txt(parte, txt, avisos, offset=offset)
                    if txt.is_file():
                        nomes.append(txt.name)
                        if avisos:
                            pp = ", ".join(str(offset + k) for k in sorted(avisos))
                            print(f"   Aviso de tabela/imagem nas paginas: {pp}")
                except Exception as e:
                    print(f"   [aviso] falha ao gerar {txt.name}: {e}")
        print(f"[OK] {arq.name} -> {', '.join(nomes)} ({n} páginas alteradas)")


if __name__ == "__main__":
    main()
