#!/usr/bin/env python3
"""
limpa_pdf_mpsc.py — v2.9 — Limpeza em lote de PDFs exportados do SIG (Softplan/MPSC)

Remove, em qualquer layout (GAECO, CAT, Promotorias...):
  1. Assinatura digital vertical da margem (texto rotacionado OU vetorizado) — sempre
  2. Carimbo "CÓPIA/COPIADO" no canto (letras e moldura tracejada) — sempre
  3. Cabeçalhos e rodapés (texto, LOGOTIPOS/imagens e linhas), por detecção
     automática de elementos repetidos entre páginas e, em documentos curtos,
     pela régua separadora da própria página (--sem-cabecalho)

Extras:
  --md      Exporta o conteúdo em Markdown estruturado (extração 100% Python;
            --txt é alias antigo e também gera .md)
  --ocr     OCR (Tesseract) nas páginas sem texto aproveitável E nas imagens
            embutidas de páginas com texto (prints, documentos anexados)
  --max-mb  Divide o resultado em partes de até N MB (padrão 100; 0 = não)

Novidades da v2.9:
  - FIM DO "APAGOU DEMAIS" (diagnóstico empírico em auditoria_limpeza.py /
    RELATORIO_APAGOU_DEMAIS.md): os cortes de cabeçalho/rodapé removiam
    QUALQUER imagem/caminho que tocasse ou cruzasse o corte (bbox[3] >=
    cut_topo - 2). Prints e certidões escaneadas do corpo terminam encostados
    na régua do cabeçalho — e eram engolidos inteiros (até 60% da página;
    56 de 81 páginas do exemplo real perdiam >30% da tinta). Correções:
      (1) REGRA DO CENTRO: o corte só remove elemento cujo CENTRO esteja na
          faixa do cabeçalho/rodapé; quem apenas encosta/cruza é conteúdo.
          Exceção única: a tarja da assinatura lateral (_eh_tarja_assinatura).
      (2) ZONAS DE TABELA (zonas_tabela): grade com >= 2 linhas horizontais e
          >= 2 verticais conectadas (ou caixa traçada) é território protegido —
          nenhuma regra heurística remove elemento com centro lá dentro (só
          assinatura e carimbo CÓPIA continuam removíveis). Recibos, prints
          emoldurados e tabelas vetoriais ficam íntegros.
      (3) RÉGUA MEDIDA, NÃO CHUTADA: _eh_regua passou de 0,72/0,18 para
          LIM_REGUA_TOPO=0,85 / LIM_REGUA_BASE=0,11 (réguas reais do acervo:
          0,864–0,908 topo, 0,068–0,094 base) e candidata cujos extremos
          coincidem com verticais é borda de CAIXA, não régua (_regua_caixa) —
          inclusive na detecção por repetição (borda de print colado na mesma
          posição em dezenas de páginas não vira mais corte).
      (4) ROLLBACK POR PÁGINA (rede de segurança SEMPRE ativa): se as regras
          heurísticas removerem >35% dos caracteres (LIMITE_PERDA_PAGINA, só
          em páginas com >= 200 chars) ou >10% da área em imagens
          (LIMITE_PERDA_AREA_IMG), a reescrita é descartada e a página fica
          intacta, com log "[protecao] pag N". Falha estruturalmente
          impossível de repetir, mesmo se uma regra futura escorregar.
    A assinatura digital (rotacionada/vetorizada/tarja), o carimbo CÓPIA e a
    remoção de cabeçalho/rodapé verdadeiros continuam EXATAMENTE como antes
    (regressão automatizada em tests/regressao/verificar_regressao.py).
  - OCR EM PARALELO POR PÁGINA (medido em perfil.py/PERFIL_*.md: o Tesseract
    era 85% do tempo de OCR, um processo por página, sequencial):
    ProcessPoolExecutor com OCR_WORKERS processos (0 = automático:
    núcleos-1 com teto por RAM; --workers na CLI e na GUI), OMP_THREAD_LIMIT=1
    por worker, worker no nível do módulo (Windows/spawn) e
    multiprocessing.freeze_support() no main (obrigatório no exe congelado).
    O resultado por página é IDÊNTICO ao sequencial (validado bit a bit);
    páginas em branco pulam o Tesseract (O4). O render em tons de cinza (O3)
    e o Otsu em cópia reduzida (O2) foram REPROVADOS/descartados no portão de
    qualidade (portao_qualidade.py) — qualidade nunca se troca por
    velocidade.
  - EXPORTAÇÃO SEM pdfplumber DESNECESSÁRIO (O5): find_tables (pdfminer) era
    ~99% do tempo do .md varrendo páginas escaneadas; agora só roda nas
    páginas onde uma varredura barata do parse pikepdf (_paginas_com_grade,
    grade traçada >= 3x3 linhas) indica tabela possível — a saída é idêntica.
  - PROGRESSO E CANCELAMENTO (Tarefa B): as funções pesadas aceitam
    progresso(etapa, feito, total, detalhe) e cancelar (threading.Event);
    planejar() conta páginas e páginas de OCR (orçamento exato p/ barra
    honesta, pesos P_* medidos no perfil). Cancelado, NADA fica pela metade:
    toda função grava só ao final.

Novidades da v2.8:
  - SAÍDA SEMPRE EM MARKDOWN (.md): título com metadados (nº do processo,
    unidade, total de páginas), "## Página N de TOTAL" contínuo entre partes,
    peças processuais como "### <PEÇA>" (PECA_ROTULOS, detecção conservadora:
    linha curta e MAIÚSCULA — prosa nunca vira heading) e tabelas Markdown
    apenas quando reais (filtro TAB_MIN_LINHAS x TAB_MIN_COLUNAS). Os avisos
    de tabela/imagem foram REMOVIDOS: o conteúdo das imagens agora é
    extraído ativamente, e aviso virou ruído para a IA.
  - OCR DE IMAGENS EMBUTIDAS: páginas com texto de corpo E prints/documentos
    anexados como imagem (prova!) passam por OCR POR REGIÃO — texto invisível
    selecionável no PDF (mesma matemática de alinhamento, deslocada pelo
    recorte) + bloco marcado "[Texto extraído de imagem...]" no .md, com
    deduplicação tolerante contra o corpo. O logo do MPSC é excluído por
    fração de área (IMG_OCR_FRAC_MIN) e zona de cabeçalho. Páginas
    MANUSCRITAS: OCR best-effort com banner explícito de baixa confiança
    (o Tesseract não lê cursiva com fidelidade — não prometemos).
  - DIVISÃO POR TAMANHO (MB): o gargalo do Copilot/IPED é o tamanho do
    arquivo, não a contagem de páginas. Partes de até --max-mb MB (padrão
    100), medindo o tamanho REAL gravado em disco (crescer-gravar-medir) —
    nunca estima, nunca perde página; página que sozinha excede o limite sai
    inteira, com aviso.

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
  python limpa_pdf_mpsc.py "C:\\pasta" --sem-cabecalho --md --ocr

Requisitos: pip install pikepdf pdfplumber pypdfium2 pytesseract
            (OCR requer também o programa Tesseract instalado)
"""

import argparse
import math
import re
import sys
from collections import defaultdict
from enum import Enum
from pathlib import Path

import pikepdf
from pikepdf import Operator, parse_content_stream, unparse_content_stream

# ----------------------------- parâmetros -----------------------------------
TOL_ROT = 0.01          # tolerância p/ considerar texto rotacionado
ZONA_TOPO = 0.30        # fração superior da página onde boilerplate pode viver
ZONA_BASE = 0.12        # fração inferior
FRACAO_REPETICAO = 0.25 # elemento repetido em >= max(3, 25% das págs) = boilerplate
CANTO_X, CANTO_Y = 200, 230   # região do carimbo CÓPIA (canto sup. esquerdo)
# Divisão por TAMANHO (v2.8): o gargalo do Copilot/IPED é o tamanho do
# arquivo, não a contagem de páginas (uma página escaneada pesa MUITAS vezes
# mais que uma só-texto). Partes de até MAX_MB_PARTE megabytes; 0 = não
# dividir. A margem deixa o arquivo final confortavelmente abaixo do teto.
MAX_MB_PARTE = 100          # tamanho máximo de cada parte, em MB
DIV_MARGEM_SEGURANCA = 0.90 # limite efetivo = max_mb * margem (folga)
# Faixas fixas (fallback p/ docs curtos, em pontos) — apenas TEXTO:
FAIXA_TOPO_TXT, FAIXA_BASE_TXT = 78, 70
CANTO_DIR_X, CANTO_DIR_Y = 400, 95

# --- Guardas contra "apagou demais" (v2.9) -----------------------------------
# Limiares de posição da régua separadora, MEDIDOS no acervo (auditoria da
# Tarefa A): réguas verdadeiras de topo ficam em 0,864–0,908 da altura e as
# de base em 0,068–0,094; candidatas FALSAS (bordas de tabela/caixa no corpo)
# apareceram em 0,757–0,846 (topo) e 0,123–0,179 (base). Os antigos 0,72/0,18
# admitiam as falsas.
LIM_REGUA_TOPO = 0.85   # régua de topo só acima desta fração da altura
LIM_REGUA_BASE = 0.11   # régua de base só abaixo desta fração
# Uma "régua" cujos DOIS extremos coincidem com linhas verticais que se
# estendem para o corpo é a borda superior/inferior de uma CAIXA (print,
# tabela) — não é régua de cabeçalho. Medido: caixas do acervo têm verticais
# exatamente nos cantos; a régua real do MPSC não tem vertical alguma.
REGUA_CANTO_TOL = 5.0    # tolerância (pt) p/ casar canto de caixa
REGUA_CANTO_MIN = 10.0   # vertical estendendo-se além disso = borda de caixa
# Zonas de tabela (C1): grade de >= 2 linhas horizontais e >= 2 verticais
# conectadas (ou retângulo traçado) é TERRITÓRIO PROTEGIDO — nenhuma regra
# heurística remove elemento cujo centro caia dentro dela (exceções:
# assinatura rotacionada/vetorial, carimbo CÓPIA e tarja de margem).
TAB_LINHA_FINA = 3.5     # espessura máx. (pt) de uma linha de grade
TAB_LINHA_H_MIN = 24.0   # comprimento mín. de linha horizontal de grade
TAB_LINHA_V_MIN = 12.0   # comprimento mín. de linha vertical de grade
TAB_RECT_MIN = 16.0      # lado mín. p/ retângulo traçado contar como caixa
TAB_RECT_MAX_FRAC = 0.85 # retângulo cobrindo >= isso da página = moldura de
                         # página, não tabela (não vira zona)
TAB_ZONA_BORDA = 0.75    # o teste de "centro dentro da zona" encolhe a zona
                         # nisto (pt): a régua do cabeçalho encosta a 1 pt da
                         # borda da caixa e é absorvida no grupo — sem o
                         # encolhimento ela ficaria protegida junto
# Tarja da assinatura digital: barra vertical estreita e alta colada à margem
# externa (medida nos exemplos: ~10 pt de largura, >= 75% da altura, x/W >=
# 0,90). Continua removível pelos cortes mesmo quando apenas cruza o corte.
ASSIN_TARJA_LARG_MAX = 20.0   # largura máxima da tarja (pt)
ASSIN_TARJA_ALT_MIN = 0.50    # altura mínima (fração da altura da página)
ASSIN_TARJA_MARGEM = 0.12     # faixa de margem externa (fração da largura)
# Rollback por página (C5 — rede de segurança): se as regras HEURÍSTICAS
# (cortes/faixas/boilerplate — não a assinatura nem o carimbo) removerem mais
# que LIMITE_PERDA_PAGINA dos caracteres da página (só avaliado a partir de
# ROLLBACK_MIN_CHARS) OU imagens somando mais que LIMITE_PERDA_AREA_IMG da
# área da página, a reescrita é DESCARTADA e a página fica intacta. Página
# normal perde 5–20% (cabeçalho+rodapé); acima disso é regra escorregando.
LIMITE_PERDA_PAGINA = 0.35    # fração máx. de chars removíveis por heurística
ROLLBACK_MIN_CHARS = 200      # páginas com menos chars não usam o critério de chars
LIMITE_PERDA_AREA_IMG = 0.10  # fração máx. da página em imagens removíveis
# Motivos CALIBRADOS (nunca disparam rollback nem respeitam zona de tabela):
MOTIVOS_CALIBRADOS = frozenset({
    "assinatura_rotacionada", "assinatura_vetorial", "carimbo_copia",
    "tarja_margem"})

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
    """Linha horizontal larga e fina (separador de cabeçalho/rodapé).

    v2.9: os limiares de posição passaram de 0,72/0,18 para
    LIM_REGUA_TOPO/LIM_REGUA_BASE, medidos no acervo (vide comentário das
    constantes): os antigos aceitavam bordas de tabela/caixa do CORPO como
    "régua", e o corte então engolia conteúdo legítimo."""
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    if w < 0.45 * W or h > 3.5:
        return None
    if bbox[1] >= H * LIM_REGUA_TOPO:
        return "topo"
    if bbox[3] <= H * LIM_REGUA_BASE:
        return "base"
    return None


def _verticais_finas(els):
    """Linhas VERTICAIS finas da página (candidatas a grade/borda de caixa).
    Só caminhos traçados ou de poucos pontos — glifos vetorizados (letras
    desenhadas como caminho preenchido) não contam."""
    out = []
    for kind, key, bbox, _ins, rot in els:
        if kind != "P" or rot or not bbox:
            continue
        w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
        if w > TAB_LINHA_FINA or h < REGUA_CANTO_MIN:
            continue
        tracado = str(key[-1]) in ("S", "s", "B", "B*", "b", "b*")
        if tracado or key[5] <= 6:
            out.append(bbox)
    return out


def _regua_caixa(bbox, verticais):
    """True se a "régua" candidata é, na verdade, a borda horizontal de uma
    CAIXA: linhas verticais finas coincidem com os DOIS extremos dela e se
    estendem REGUA_CANTO_MIN ou mais para além (o interior da caixa). A régua
    real do cabeçalho MPSC é solitária — não tem verticais nos cantos."""
    y = (bbox[1] + bbox[3]) / 2
    for xe in (bbox[0], bbox[2]):
        for vb in verticais:
            vx = (vb[0] + vb[2]) / 2
            if abs(vx - xe) <= REGUA_CANTO_TOL \
                    and vb[1] <= y + REGUA_CANTO_TOL \
                    and vb[3] >= y - REGUA_CANTO_TOL \
                    and (y - vb[1] >= REGUA_CANTO_MIN
                         or vb[3] - y >= REGUA_CANTO_MIN):
                break
        else:
            return False
    return True


def zonas_tabela(els, W, H, so_tracadas=False, min_h=2, min_v=2):
    """Zonas de TABELA/CAIXA da página (C1 — território protegido).

    Reaproveita os elementos já parseados pelo pikepdf (sem pdfplumber):
    coleta linhas horizontais finas, linhas verticais finas e retângulos
    traçados (caixas — viram 2 linhas H + 2 V); agrupa as linhas que se
    tocam (tolerância 3 pt) e considera TABELA todo grupo com >= 2 linhas
    horizontais E >= 2 verticais (o filtro mínimo 2x2 que evita falso
    positivo com texto justificado). Retângulo cobrindo quase a página toda
    (>= TAB_RECT_MAX_FRAC) é moldura de página, não tabela. Devolve a lista
    de bboxes das zonas.

    'so_tracadas=True' considera apenas linhas TRAÇADAS (stroke) — o modo do
    gate do pdfplumber (O5): em páginas de texto vetorizado do SIG, glifos
    preenchidos de poucos pontos ("l", "1", "-") viram falsas "linhas" e
    quase toda página ganharia zona. Para a PROTEÇÃO (C1) o padrão continua
    incluindo linhas preenchidas finas: falso positivo lá só protege a mais
    (conservador, CLAUDE.md §5)."""
    horiz, vert = [], []
    area_pag = (W * H) or 1
    for kind, key, bbox, _ins, rot in els:
        if kind != "P" or rot or not bbox:
            continue
        w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
        tracado = str(key[-1]) in ("S", "s", "B", "B*", "b", "b*")
        if not (tracado or (key[5] <= 6 and not so_tracadas)):
            continue  # glifo vetorizado/desenho: não é linha de grade
        if h <= TAB_LINHA_FINA and w >= TAB_LINHA_H_MIN:
            horiz.append(bbox)
        elif w <= TAB_LINHA_FINA and h >= TAB_LINHA_V_MIN:
            vert.append(bbox)
        elif tracado and w >= TAB_RECT_MIN and h >= TAB_RECT_MIN \
                and key[5] <= 6 and (w * h) < area_pag * TAB_RECT_MAX_FRAC:
            # retângulo traçado (caixa de print/recibo): borda = 2 H + 2 V
            horiz.append((bbox[0], bbox[1], bbox[2], bbox[1]))
            horiz.append((bbox[0], bbox[3], bbox[2], bbox[3]))
            vert.append((bbox[0], bbox[1], bbox[0], bbox[3]))
            vert.append((bbox[2], bbox[1], bbox[2], bbox[3]))
    linhas = [(b, True) for b in horiz] + [(b, False) for b in vert]
    n = len(linhas)
    if n < 4:
        return []

    # união-busca por interseção (com tolerância de 3 pt)
    pai = list(range(n))

    def achar(a):
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    def toca(a, b):
        return not (a[2] < b[0] - 3 or b[2] < a[0] - 3
                    or a[3] < b[1] - 3 or b[3] < a[1] - 3)

    for i in range(n):
        for j in range(i + 1, n):
            if toca(linhas[i][0], linhas[j][0]):
                ra, rb = achar(i), achar(j)
                if ra != rb:
                    pai[ra] = rb
    grupos = defaultdict(lambda: [0, 0, None])  # nH, nV, bbox união
    for i, (b, eh_h) in enumerate(linhas):
        g = grupos[achar(i)]
        g[0] += 1 if eh_h else 0
        g[1] += 0 if eh_h else 1
        u = g[2]
        g[2] = b if u is None else (min(u[0], b[0]), min(u[1], b[1]),
                                    max(u[2], b[2]), max(u[3], b[3]))
    return [g[2] for g in grupos.values() if g[0] >= min_h and g[1] >= min_v]


def _centro_em_zonas(bbox, zonas):
    """True se o CENTRO do bbox cai dentro de alguma zona de tabela.

    O teste é ESTRITO (zona encolhida em TAB_ZONA_BORDA): a régua do
    cabeçalho/rodapé costuma encostar a 1–3 pt da borda de uma caixa de
    print e acaba unida ao grupo da grade; sem o encolhimento ela ficaria
    "dentro" da zona e protegida — e a moldura deixaria de ser removida.
    As bordas da própria caixa ficam >= 1 pt para dentro do limite do grupo
    (a régua alheia é que o estica) e continuam protegidas."""
    if not zonas or not bbox:
        return False
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    t = TAB_ZONA_BORDA
    return any(z[0] + t <= cx <= z[2] - t and z[1] + t <= cy <= z[3] - t
               for z in zonas)


def _eh_tarja_assinatura(bbox, W, H):
    """Barra vertical estreita e alta colada à margem EXTERNA: a tarja de
    fundo da assinatura digital lateral. Nunca é conteúdo do miolo, então os
    cortes continuam podendo removê-la mesmo quando ela cruza o corte."""
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    if w > ASSIN_TARJA_LARG_MAX or h < H * ASSIN_TARJA_ALT_MIN:
        return False
    return bbox[0] >= W * (1 - ASSIN_TARJA_MARGEM) \
        or bbox[2] <= W * ASSIN_TARJA_MARGEM


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
    é estendido para baixo até englobá-las.

    v2.9: candidata cujos extremos coincidem com verticais (borda de CAIXA —
    print, recibo, tabela) é descartada (_regua_caixa): não é régua."""
    verticais = _verticais_finas(els)
    reg_topo, reg_base = [], []
    for kind, key, bbox, instrs, rot in els:
        if kind == "P" and bbox and not rot:
            lado = _eh_regua(bbox, W, H)
            if lado and _regua_caixa(bbox, verticais):
                continue  # borda de caixa/tabela, não régua de cabeçalho
            if lado == "topo":
                reg_topo.append(bbox[1])
            elif lado == "base":
                reg_base.append(bbox[3])
    cut_topo = min(reg_topo) if reg_topo else None
    cut_base = max(reg_base) if reg_base else None
    # Salvaguardas: a régua de topo não pode invadir o corpo nem a de base
    # subir demais (mesmos limiares medidos de _eh_regua).
    if cut_topo is not None and cut_topo < H * LIM_REGUA_TOPO:
        cut_topo = None
    if cut_base is not None and cut_base > H * LIM_REGUA_BASE:
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


def analisar(pdf, progresso=None):
    """Pass A (1 leitura por página). Vide reescrever() para o uso.
    'progresso' (v2.9/B): callable opcional progresso(etapa, feito, total,
    detalhe) — o núcleo NÃO conhece Qt; a GUI adapta para sinal."""
    contagem = defaultdict(set)
    zonas = {}
    tam_grupo = defaultdict(int)
    reguas = defaultdict(lambda: defaultdict(list))
    n_total = len(pdf.pages)
    for i, page in enumerate(pdf.pages):
        if progresso:
            progresso("analise", i + 1, n_total, f"página {i + 1}")
        g = _grupo(page)
        tam_grupo[g] += 1
        W, H = g
        els = _elementos(page)
        if els is None:
            continue
        verticais = _verticais_finas(els)
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
                # v2.9: borda de caixa repetida (prints colados na mesma
                # posição em muitas páginas) NÃO pode virar régua — era o
                # mecanismo que propagava o corte para dentro do conteúdo.
                if lado and not _regua_caixa(bbox, verticais):
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


def _motivo_bruto(i, kind, key, bbox, rot, ctx):
    """Decisão de remoção SEM a guarda de zona de tabela (vide
    _motivo_remocao). Devolve o MOTIVO (string) ou None (mantém)."""
    g = ctx["g"]; W = ctx["W"]; H = ctx["H"]
    cut_topo = ctx["cut_topo"]; cut_base = ctx["cut_base"]
    sem_cabecalho = ctx["sem_cabecalho"]

    if i in ctx["drop_ix"]:
        return "cluster_topo"
    if rot:
        return "assinatura_rotacionada"
    faixa_assin = ctx["faixa_assin"]
    if faixa_assin and kind == "P" and bbox and \
            bbox[0] >= faixa_assin[0] and bbox[2] <= faixa_assin[1]:
        return "assinatura_vetorial"  # glifo da assinatura vertical vetorizada
    if kind == "T":
        if sem_cabecalho and bbox:
            if (g, key) in ctx["boiler"]:
                return "boiler_texto"
            if cut_topo is not None and bbox[1] >= cut_topo - 1:
                return "corte_topo"
            if cut_base is not None and bbox[3] <= cut_base + 1:
                return "corte_base"
            if bbox[1] >= H - FAIXA_TOPO_TXT:
                return "faixa_fixa_topo_txt"
            if bbox[3] <= FAIXA_BASE_TXT:
                return "faixa_fixa_base_txt"
            if bbox[1] >= H - CANTO_DIR_Y and bbox[0] >= CANTO_DIR_X:
                return "canto_direito"
        return None
    if kind == "P" and bbox and ctx["spans_rem"] and \
            bbox[1] >= H * (1 - ZONA_TOPO) and \
            any(x0 - 12 <= bbox[0] and bbox[2] <= x1 + 12 and abs(bbox[1] - y) <= 7
                for x0, y, x1 in ctx["spans_rem"]):
        return "glifo_orfao"  # glifo colado a uma linha removida (ex.: cedilha)
    if kind in ("P", "I", "II"):
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
        if img_pagina_inteira or i in ctx["tiras_corpo"]:
            return None  # protege o corpo escaneado
        if bbox and tracado and bbox[2] <= CANTO_X and bbox[1] >= H - CANTO_Y:
            return "carimbo_copia"  # moldura do carimbo (contorno tracejado)
        if sem_cabecalho and bbox:
            if kind in ("I", "II") and (g, key) in ctx["boiler"]:
                return "boiler_imagem"
            if kind == "P" and (g, key) in ctx["boiler_base_P"]:
                return "boiler_path"
            centro_y = (bbox[1] + bbox[3]) / 2
            # v2.9 (fix do "apagou demais"): o corte só remove o elemento se
            # o CENTRO dele estiver dentro da faixa do cabeçalho/rodapé. A
            # regra antiga removia QUALQUER elemento que tocasse/cruzasse o
            # corte (bbox[3] >= cut_topo - 2) — e as imagens do corpo
            # (prints, certidões escaneadas) terminam encostadas na régua do
            # cabeçalho, então eram engolidas INTEIRAS. Única exceção: a
            # tarja da assinatura lateral (nunca é conteúdo do miolo).
            if cut_topo is not None and bbox[3] >= cut_topo - 2:
                if centro_y >= cut_topo - 2:
                    return "corte_topo"  # majoritariamente acima do corte
                if _eh_tarja_assinatura(bbox, W, H):
                    return "tarja_margem"
                # cruza o corte mas vive no corpo: conteúdo — mantém
            if cut_base is not None and bbox[1] <= cut_base + 2:
                if centro_y <= cut_base + 2:
                    return "corte_base"  # majoritariamente abaixo do corte
                if _eh_tarja_assinatura(bbox, W, H):
                    return "tarja_margem"
            if kind == "P" and bbox[3] <= H * 0.12 and \
                    any(lo <= bbox[1] <= hi for lo, hi in ctx["faixas_base"].get(g, ())):
                return "faixa_base_vetorial"  # varredura do rodapé vetorizado
    return None


def _motivo_remocao(i, kind, key, bbox, rot, ctx):
    """Decide se o elemento deve ser removido e POR QUAL REGRA.

    Devolve o MOTIVO (string) ou None (mantém). Substitui o antigo 'bool
    drop': a mesma decisão, mas rastreável — a auditoria (auditoria_limpeza)
    agrega a perda por motivo para diagnosticar 'apagou demais' sem
    adivinhação. ctx é o dicionário montado por reescrever() com o estado da
    página (cortes, boiler, faixas etc.).

    v2.9 — zona de tabela é território protegido (C1): elemento cujo centro
    cai dentro de uma grade/caixa detectada (zonas_tabela) NÃO é removido
    pelas regras heurísticas; só a assinatura (rotacionada/vetorial/tarja) e
    o carimbo CÓPIA continuam removíveis lá dentro."""
    motivo = _motivo_bruto(i, kind, key, bbox, rot, ctx)
    if motivo and motivo not in MOTIVOS_CALIBRADOS \
            and _centro_em_zonas(bbox, ctx.get("zonas_tabela")):
        return None
    return motivo


def _chars_mostrados(instrs) -> int:
    """Nº de caracteres exibidos (operandos de Tj/TJ/'/\") nas instruções.
    Usado pelo rollback (C5) para medir a perda de texto por página sem
    reextrair o PDF."""
    n = 0
    for item in instrs:
        operands, op = item[0], item[1]
        if op not in OPS_SHOW:
            continue
        try:
            fonte = operands[0] if op == Operator("TJ") else operands
            for el in fonte:
                if isinstance(el, (pikepdf.String, str, bytes)):
                    n += len(str(el))
        except Exception:
            pass
    return n


def reescrever(pdf, page, idx, boiler, boiler_base_P, cortes, faixas_base,
               sem_cabecalho, auditoria=None):
    """Reescreve a página removendo moldura. 'auditoria', se fornecida, é uma
    LISTA onde cada remoção é registrada como (motivo, kind, bbox) — usada
    pelo modo --auditar (auditoria_limpeza.py) para diagnosticar perdas.

    Retorna (alterado, protegido): 'protegido' = True quando o rollback (C5)
    descartou a reescrita por remoção excessiva (a página fica intacta)."""
    g = _grupo(page)
    W, H = g
    cut_topo, cut_base = cortes.get(idx, (None, None))
    els = _elementos(page)
    if els is None:
        return False, False

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

    ctx = {
        "g": g, "W": W, "H": H, "cut_topo": cut_topo, "cut_base": cut_base,
        "sem_cabecalho": sem_cabecalho, "drop_ix": drop_ix,
        "spans_rem": spans_rem, "faixa_assin": faixa_assin,
        "tiras_corpo": tiras_corpo, "boiler": boiler,
        "boiler_base_P": boiler_base_P, "faixas_base": faixas_base,
        # C1 (v2.9): grades/caixas detectadas viram território protegido.
        "zonas_tabela": zonas_tabela(els, W, H) if sem_cabecalho else [],
    }

    novas = []
    alterado = False
    # Rollback (C5): mede o que as regras HEURÍSTICAS estão levando. As
    # remoções calibradas (assinatura, carimbo, tarja) ficam de fora — elas
    # nunca podem deixar de acontecer.
    chars_total = 0
    chars_heur = 0
    area_img_heur = 0.0
    remocoes = []
    for i, (kind, key, bbox, instrs, rot) in enumerate(els):
        motivo = _motivo_remocao(i, kind, key, bbox, rot, ctx)
        remocoes.append(motivo)
        if kind == "T":
            n = _chars_mostrados(instrs)
            chars_total += n
            if motivo and motivo not in MOTIVOS_CALIBRADOS:
                chars_heur += n
        elif kind in ("I", "II") and bbox and motivo \
                and motivo not in MOTIVOS_CALIBRADOS:
            area_img_heur += max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

    perda_chars = chars_heur / chars_total if chars_total else 0.0
    perda_area = area_img_heur / ((W * H) or 1)
    if (chars_total >= ROLLBACK_MIN_CHARS and perda_chars > LIMITE_PERDA_PAGINA) \
            or perda_area > LIMITE_PERDA_AREA_IMG:
        det = (f"{perda_chars * 100:.0f}% dos caracteres"
               if perda_chars > LIMITE_PERDA_PAGINA
               else f"{perda_area * 100:.0f}% da área em imagens")
        print(f"   [protecao] pag {idx + 1}: remocao excessiva ({det}) — "
              "pagina mantida intacta.", flush=True)
        return False, True

    for i, (kind, key, bbox, instrs, rot) in enumerate(els):
        motivo = remocoes[i]
        if motivo:
            alterado = True
            if auditoria is not None:
                auditoria.append((motivo, kind, bbox))
        else:
            novas.extend(instrs)

    if alterado:
        page.Contents = pdf.make_stream(unparse_content_stream(novas))
    return alterado, False


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


# Limiar de área (fração da página) acima do qual a imagem É a própria página
# (página escaneada/desenhada): protegida na limpeza e coberta pelo OCR de
# página inteira.
IMG_PAGINA_FRAC = 0.80     # >= 80% da página = a própria página é imagem

# --------------------------- exportação em Markdown (v2.8) ------------------
# A saída de texto é SEMPRE Markdown: título com metadados, "## Página N de
# TOTAL" por página e "### <peça>" quando uma linha inicia peça processual.
TAB_MIN_LINHAS = 2     # tabela real tem >= 2 linhas E >= 2 colunas — abaixo
TAB_MIN_COLUNAS = 2    # disso é o falso positivo do find_tables em prosa
PECA_MAX_LINHA = 60    # linha candidata a rótulo de peça deve ser CURTA
# Rótulos que abrem peça processual ("###" no .md). Conservador (CLAUDE.md
# §5): a linha inteira precisa ser MAIÚSCULA, curta e COMEÇAR com um rótulo;
# na dúvida, texto corrido nunca vira heading. Estenda aqui quando necessário.
PECA_ROTULOS = (
    "DESPACHO", "CERTIDÃO", "CERTIDAO", "PORTARIA", "INFORMAÇÃO",
    "INFORMACAO", "OFÍCIO", "OFICIO", "PROMOÇÃO", "PROMOCAO",
    "DECISÃO", "DECISAO", "RELATÓRIO", "RELATORIO", "TERMO DE",
)
# Nº de processo do SIG (ex.: 09.2023.00003077-4) e linha da unidade, para o
# cabeçalho de metadados do .md (ambos opcionais — só entram se detectados).
PROC_REGEX = re.compile(r"\b\d{2}\.\d{4}\.\d{8}-\d\b")
UNIDADE_REGEX = re.compile(
    r"(?im)^[^\n]{0,80}(?:promotoria|procuradoria)[^\n]{0,80}$")
# Confiança média (0-100) abaixo da qual um bloco de OCR de imagem embutida é
# marcado no .md como "baixa confiança — conferir no original".
IMG_OCR_CONF_BAIXA = 60


def _detectar_peca(linha: str):
    """Rótulo da peça se a LINHA inicia uma peça processual; senão None.
    Conservador (CLAUDE.md §5): só linha CURTA, toda MAIÚSCULA e começando
    com um PECA_ROTULOS seguido de fim/não-letra — prosa nunca vira heading."""
    s = " ".join((linha or "").split())
    if not s or len(s) > PECA_MAX_LINHA or s != s.upper():
        return None
    for rot in PECA_ROTULOS:
        if s.startswith(rot):
            resto = s[len(rot):]
            if not resto or not resto[0].isalpha():
                return s
    return None


def _marcar_pecas(texto: str) -> str:
    """Insere '---' + '### <peça>' nas linhas que iniciam peça processual."""
    out = []
    for linha in texto.splitlines():
        rot = _detectar_peca(linha)
        if rot:
            if out and out[-1].strip():
                out.append("")
            out += ["---", "", f"### {rot}", ""]
        else:
            out.append(linha)
    return "\n".join(out)


def _tabela_para_md(linhas):
    """Converte a matriz do pdfplumber em tabela Markdown; None se não passar
    no filtro mínimo TAB_MIN_LINHAS x TAB_MIN_COLUNAS (o find_tables lê
    espaços de prosa justificada como colunas — falso positivo, CLAUDE.md §4).
    Fora de tabela validada, o .md NUNCA recebe pipes."""
    linhas = [l for l in (linhas or []) if l and any(c for c in l)]
    if len(linhas) < TAB_MIN_LINHAS:
        return None
    ncol = max(len(l) for l in linhas)
    if ncol < TAB_MIN_COLUNAS:
        return None

    def cel(c):
        return (" ".join(str(c).split()) if c else "").replace("|", "\\|")

    out = []
    for i, l in enumerate(linhas):
        l = list(l) + [None] * (ncol - len(l))
        out.append("| " + " | ".join(cel(c) for c in l) + " |")
        if i == 0:
            out.append("|" + " --- |" * ncol)
    return "\n".join(out)


def _paginas_com_grade(pdf_path: Path):
    """Páginas (0-based) que têm GRADE vetorial (>= 2 linhas H e >= 2 V
    conectadas — vide zonas_tabela), ou seja: as únicas onde o find_tables
    do pdfplumber (estratégia de linhas) pode achar tabela real.

    v2.9/O5: o pdfplumber usa pdfminer, ordens de grandeza mais lento que o
    parse do pikepdf que já fazemos — no perfil, 125 s dos 127 s da
    exportação eram find_tables varrendo páginas ESCANEADAS sem nenhuma
    linha vetorial. Esta varredura barata restringe o pdfplumber às páginas
    com grade. Nunca quebra: erro -> None (pdfplumber roda em todas)."""
    try:
        out = set()
        with pikepdf.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                els = _elementos(page)
                if els is None:
                    out.add(i)   # não deu para analisar: na dúvida, verifica
                    continue
                W, H = _grupo(page)
                # >= 3 linhas em cada direção: uma CAIXA simples (2H+2V, uma
                # célula só) nunca passa no filtro TAB_MIN 2x2 do
                # _tabela_para_md — rodar o pdfplumber nela é custo puro.
                if zonas_tabela(els, W, H, so_tracadas=True,
                                min_h=3, min_v=3):
                    out.add(i)
        return out
    except Exception:
        return None


def _tabelas_md(pdf_path: Path) -> dict:
    """Tabelas REAIS por página (0-based nesta parte), já em Markdown.
    Nunca quebra: sem pdfplumber (ou erro), devolve {} silenciosamente.
    v2.9/O5: o pdfplumber só é aberto/rodado nas páginas com grade vetorial
    (_paginas_com_grade) — a saída é a mesma, sem o custo do pdfminer em
    páginas escaneadas/sem tabela."""
    grade = _paginas_com_grade(pdf_path)
    if grade is not None and not grade:
        return {}
    try:
        import pdfplumber
    except Exception:
        return {}
    out = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, p in enumerate(pdf.pages):
                if grade is not None and i not in grade:
                    continue
                try:
                    mds = [m for m in (_tabela_para_md(t)
                                       for t in (p.extract_tables() or [])) if m]
                except Exception:
                    continue
                if mds:
                    out[i] = mds
    except Exception:
        return {}
    return out


def _remover_sufixo_tolerante(corpo: str, sufixo: str):
    """Remove 'sufixo' do FIM de 'corpo', tolerando diferenças de espaçamento
    (a extração pode trocar espaços por quebras). None se não for sufixo.
    Usado para não duplicar no .md o texto da camada invisível de OCR de
    imagem embutida, que a extração devolve no fim do corpo da página."""
    i, j = len(corpo) - 1, len(sufixo) - 1
    while True:
        while i >= 0 and corpo[i].isspace():
            i -= 1
        while j >= 0 and sufixo[j].isspace():
            j -= 1
        if j < 0:
            return corpo[:i + 1].rstrip()
        if i < 0 or corpo[i] != sufixo[j]:
            return None
        i -= 1
        j -= 1


def _extrair_paginas(pdf_path: Path):
    """Texto de cada página (pypdfium2; pdfplumber de reserva) ou None."""
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            paginas = []
            for i in range(len(doc)):
                tp = doc[i].get_textpage()
                paginas.append((tp.get_text_range() or "").strip())
                tp.close()
            return paginas
        finally:
            doc.close()
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pl:
            return [(p.extract_text() or "").strip() for p in pl.pages]
    except Exception as e:
        print(f"   [aviso] .md nao gerado ({e}). Rode no terminal:"
              "  python -m pip install pypdfium2")
        return None


def _cabecalho_md(pdf_path: Path, paginas, total: int) -> str:
    """Título do .md: nome do arquivo + metadados detectáveis (nº do processo
    e unidade, se aparecerem nas 2 primeiras páginas) + total de páginas."""
    nome = re.sub(r"_parte\d+$", "", pdf_path.stem)
    amostra = "\n".join(paginas[:2])
    meta = []
    m = PROC_REGEX.search(amostra)
    if m:
        meta.append(f"**Processo:** {m.group(0)}")
    m = UNIDADE_REGEX.search(amostra)
    if m:
        meta.append(f"**Unidade:** {' '.join(m.group(0).split())}")
    meta.append(f"**Total de páginas:** {total}")
    return f"# {nome}\n\n" + " · ".join(meta)


def exportar_md(pdf_path: Path, md_path: Path, offset: int = 1,
                total: int = 0, info_ocr: dict | None = None,
                progresso=None, cancelar=None):
    """Gera o .md estruturado desta parte do PDF (v2.8; substitui o .txt).

    'offset' é o número (1-based) da 1ª página desta parte no documento
    inteiro (numeração CONTÍNUA, casando com o carimbo do PDF). 'total' é o
    total de páginas do documento inteiro (0 = calcula desta parte).
    'info_ocr' vem de embutir_ocr, indexado por página GLOBAL 0-based:
    {"blocos": [(texto, conf_media)], "manuscrito": bool} — blocos viram
    citações marcadas "[Texto extraído de imagem...]"; páginas manuscritas
    ganham o banner de baixa confiança. Sem avisos de tabela/imagem: o
    conteúdo das imagens agora é extraído ativamente."""
    paginas = _extrair_paginas(pdf_path)
    if paginas is None:
        return
    info_ocr = info_ocr or {}
    if not total:
        total = offset - 1 + len(paginas)
    tabelas = _tabelas_md(pdf_path)
    aviso_sem_texto = ("_(página sem texto aproveitável — ative o OCR, com o"
                       " Tesseract disponível, para extrair o conteúdo)_")

    saida = [_cabecalho_md(pdf_path, paginas, total)]
    for i, texto in enumerate(paginas):
        if cancelar is not None and cancelar.is_set():
            return   # sem gravar: nunca fica .md pela metade
        if progresso:
            progresso("exportacao", i + 1, len(paginas), f"página {offset + i}")
        num = offset + i
        info = info_ocr.get(offset - 1 + i, {})
        blocos = info.get("blocos", [])
        corpo = texto.strip()
        # O fim do texto extraído é, na ordem do content stream: corpo
        # original + camada invisível de OCR de imagem + carimbo de paginação
        # (numerar_paginas roda DEPOIS do OCR). Remove-se do fim: (1) o
        # carimbo "[Pagina N de TOTAL]" — redundante com o "## Página N" do
        # cabeçalho —, (2) os blocos de OCR de imagem, para o bloco marcado
        # abaixo não duplicar. Se não casar (extrator reordenou), mantém —
        # duplicar é aceitável, perder não.
        novo = _remover_sufixo_tolerante(corpo, _rotulo_pagina(num, total))
        if novo is not None:
            corpo = novo
        for btexto, _conf in reversed(blocos):
            novo = _remover_sufixo_tolerante(corpo, btexto)
            if novo is not None:
                corpo = novo
        if not corpo and not blocos:
            corpo = aviso_sem_texto
        elif corpo and not _texto_e_aproveitavel(corpo) and not blocos \
                and not info.get("manuscrito"):
            corpo = aviso_sem_texto
        else:
            corpo = _marcar_pecas(corpo)
        sec = [f"## Página {num} de {total}", ""]
        if info.get("manuscrito"):
            sec += ["> **[Documento manuscrito — OCR de baixa confiança,"
                    " revisar no original]**", ""]
        sec.append(corpo)
        for t in tabelas.get(i, []):
            sec += ["", t]
        for btexto, conf in blocos:
            sec += ["", f"> **[Texto extraído de imagem na página {num}]**"]
            sec += ["> " + l for l in btexto.splitlines() if l.strip()]
            if conf < IMG_OCR_CONF_BAIXA:
                sec.append("> _(baixa confiança de OCR — conferir no"
                           " original)_")
        saida.append("\n".join(sec))
    md_path.write_text("\n\n".join(saida) + "\n", encoding="utf-8")


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

# --- Desempenho do OCR (v2.9, Tarefa C — decidido por MEDIÇÃO) --------------
# PERFIL_ANTES.md: image_to_data = 85% do tempo de OCR (um processo Tesseract
# por página, sequencial). O ganho vem de paralelizar por página (O1); o
# bilateralFilter, suspeito nº 1 do prompt, mediu só 1,6 s em 261 s (0,6%) e
# foi mantido como está (qualquer risco de qualidade é veto — C.0).
OCR_WORKERS = 0          # nº de processos de OCR; 0 = automático
                         # (min(núcleos-1, RAM_GB//2), mínimo 1)
OCR_RENDER_CINZA = False # O3 (render direto em cinza) foi REPROVADO no
                         # portão de qualidade: 99,61% dos chars (< 99,9%)
                         # com divergências reais em scans degradados — o
                         # antialiasing do render RGB->L difere do render L.
                         # Mantido o caminho RGB da v2.8. NÃO ligar sem
                         # repassar o portão (portao_qualidade.py).
OCR_BRANCO_LIMIAR = 128  # página/região binarizada SEM nenhum pixel abaixo
                         # disso está em branco: pula o Tesseract (O4)

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

# --- OCR por REGIÃO de imagem embutida (v2.8) --------------------------------
# Páginas com texto de corpo podem trazer PRINTS/documentos como imagens
# embutidas (prova!) que o fluxo de página inteira nunca lia. Filtro de
# candidatas (medido nos exemplos reais): logo do MPSC ~0.014 da página;
# prints 0.024-0.063. O corte em 0.02 exclui o logo e mantém os prints.
IMG_OCR_FRAC_MIN = 0.02        # fração mínima da página p/ OCR de região
IMG_OCR_ZONA_CABECALHO = 0.15  # topo da página onde imagem = logo/timbre
# Deduplicação tolerante: fração mínima de palavras (>=4 letras) do texto da
# imagem presentes no corpo para considerá-lo repetido (e não duplicar).
OCR_DEDUP_FRAC = 0.80
# Página MANUSCRITA (best-effort honesto): quase sem texto de corpo e com
# imagem grande. O Tesseract NÃO lê cursiva com fidelidade — o .md marca.
# Medido no exemplo real: 18 chars/página + imagens de fração 0.33.
MANUSCRITO_MAX_TEXTO = 40    # corpo com menos chars que isso = "sem texto"
MANUSCRITO_FRAC_MIN = 0.25   # imagem com fração >= isso = possível manuscrito

# --- Classificador de tipo de página (v2.10, e-proc/TJSC) --------------------
# PDFs do e-proc/TJSC desenham o scan DENTRO de um Form XObject (Do de /TPLn),
# que _iter_elementos não enxerga (não desce em forms). A detecção abaixo é
# usada SÓ pelo classificador — a lógica de limpeza não muda, para as decisões
# nos arquivos do SIG permanecerem idênticas (tests/regressao/decisoes_ocr.py).
CLAS_RENDER_ESCALA = 1.0     # render p/ medir tinta: 1.0 = 72 dpi (ms/página)
CLAS_LIMIAR_TINTA = 128      # pixel de cinza < isso = "tinta" (texto/traço)
CLAS_MIN_PX_SCAN = 300_000   # imagem com >= isso px dentro de form = scan de
                             # página (ex1.pdf: 3,9 Mpx; logos/QR ficam ordens
                             # de grandeza abaixo)
# Densidade mínima (chars extraídos por 1000 px de tinta a 72 dpi) para a
# camada de texto de uma página HÍBRIDA (scan + texto) ser SUFICIENTE.
# Medido em ex1.pdf (RELATORIO_EPROC.md): páginas nativas boas medem
# 54,6-65,5; híbridas cujo texto é só a moldura do e-proc, 1,3-40,6.
# O valor fica no meio do vão. Abaixo dele, a camada é DEFICIENTE e o modo
# --reocr-hibrido=auto roda o OCR próprio (aditivo: nada é removido).
FRAC_TEXTO_MIN_HIBRIDO = 45.0
# Política padrão para páginas híbridas: "auto" reusa a camada existente
# quando suficiente e roda OCR próprio só nas deficientes; "nunca" sempre
# reusa (conservador puro); "sempre" força o reOCR (lento, pode não melhorar).
REOCR_HIBRIDO_PADRAO = "auto"


class TipoPagina(Enum):
    """Classificação de página (v2.10): UMA decisão por página, calculada na
    pré-passagem de embutir_ocr e repassada à exportação via info_ocr."""
    NATIVA_DIGITAL = "nativa"        # texto real, sem scan de página inteira
    HIBRIDA_COM_OCR = "hibrida"      # scan de página + camada de texto boa
    IMAGEM_SEM_OCR = "imagem"        # scan sem camada de texto (OCR próprio)
    TEXTO_CORROMPIDO = "corrompida"  # camada é lixo (remove + OCR próprio)


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


def _form_tem_imagem_grande(xo, nivel=0):
    """True se o Form XObject contém (recursivamente, até 3 níveis) uma
    imagem "de scan" (>= CLAS_MIN_PX_SCAN pixels)."""
    if nivel > 3:
        return False
    try:
        sub = xo.get("/Resources", None)
        xobjs = dict(sub.get("/XObject", {})) if sub is not None else {}
    except Exception:
        return False
    for _nome, o in xobjs.items():
        try:
            st = str(o.get("/Subtype", ""))
            if st == "/Image":
                if int(o.get("/Width", 0)) * int(o.get("/Height", 0)) \
                        >= CLAS_MIN_PX_SCAN:
                    return True
            elif st == "/Form" and _form_tem_imagem_grande(o, nivel + 1):
                return True
        except Exception:
            continue
    return False


def _bbox_scan_form(page):
    """Bbox (pontos de página) da colocação de um Form XObject que carrega o
    SCAN da página inteira — o arranjo do e-proc/TJSC —, ou None.

    Rastreia o CTM (q/Q/cm) no stream DE PÁGINA; para cada Do de Form cujo
    conteúdo tem imagem grande (_form_tem_imagem_grande), projeta o /BBox do
    form (com o /Matrix) pela CTM e aceita se cobrir >= IMG_PAGINA_FRAC da
    largura E da altura. Usado SÓ pelo classificador (v2.10)."""
    try:
        instrs = parse_content_stream(page)
    except Exception:
        return None
    res = page.get("/Resources", None)
    xobjs = res.get("/XObject", None) if res is not None else None
    if xobjs is None:
        return None
    xobjs = dict(xobjs)
    W, H = _grupo(page)
    if not W or not H:
        return None
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
        elif o == "Do" and operands:
            xo = xobjs.get(operands[0])
            if xo is None:
                continue
            try:
                if str(xo.get("/Subtype", "")) != "/Form":
                    continue
                if not _form_tem_imagem_grande(xo):
                    continue
                bb = [float(v) for v in xo.get("/BBox")]
                m = xo.get("/Matrix", None)
                m = tuple(float(v) for v in m) if m is not None else I
            except Exception:
                continue
            mt = mul(m, ctm)
            xs, ys = [], []
            for x, y in ((bb[0], bb[1]), (bb[2], bb[1]),
                         (bb[0], bb[3]), (bb[2], bb[3])):
                xs.append(mt[0] * x + mt[2] * y + mt[4])
                ys.append(mt[1] * x + mt[3] * y + mt[5])
            bbox = (min(xs), min(ys), max(xs), max(ys))
            if (bbox[2] - bbox[0]) >= W * IMG_PAGINA_FRAC \
                    and (bbox[3] - bbox[1]) >= H * IMG_PAGINA_FRAC:
                return bbox
    return None


def _densidade_texto(pg_pdfium, texto: str) -> float:
    """Chars não-brancos por 1000 pixels de tinta, num render rápido em baixa
    resolução (CLAS_RENDER_ESCALA). Página sem tinta devolve infinito — sem
    tinta não há o que recuperar, logo a camada nunca é "deficiente"."""
    try:
        img = pg_pdfium.render(scale=CLAS_RENDER_ESCALA).to_pil().convert("L")
        hist = img.histogram()
        px_tinta = sum(hist[:CLAS_LIMIAR_TINTA])
    except Exception:
        return float("inf")
    if not px_tinta:
        return float("inf")
    chars = sum(1 for c in (texto or "") if not c.isspace())
    return chars / px_tinta * 1000.0


def classificar_pagina(page_pike, pg_pdfium, texto: str):
    """Classifica UMA página (atl.md §5): devolve (TipoPagina,
    camada_deficiente, bbox_scan).

    - NATIVA_DIGITAL: texto aproveitável, sem scan de página inteira;
    - HIBRIDA_COM_OCR: scan de página inteira + texto aproveitável (caso
      e-proc). 'camada_deficiente' = True quando a densidade do texto fica
      abaixo de FRAC_TEXTO_MIN_HIBRIDO (a camada diz muito menos do que a
      tinta visível sugere — ex.: só a moldura do e-proc);
    - TEXTO_CORROMPIDO: há camada (>= OCR_MIN_CHARS_AVAL) mas é lixo;
    - IMAGEM_SEM_OCR: sem camada útil.

    'bbox_scan' (pontos de página) é a colocação do scan quando conhecida —
    usada pelo OCR de região das híbridas deficientes. 'camada_deficiente'
    só pode ser True para HIBRIDA_COM_OCR: páginas nativas (todo o acervo
    do SIG com texto) NUNCA são afetadas pela verificação de densidade."""
    aproveitavel = _texto_e_aproveitavel(texto)
    els = _elementos(page_pike)
    W, H = _grupo(page_pike)
    inteira = False
    bbox_scan = None
    for kind, _k, b, _i, rot in (els or []):      # detecção viva (SIG)
        if kind in ("I", "II") and b and not rot and W and H \
                and (b[2] - b[0]) >= W * IMG_PAGINA_FRAC \
                and (b[3] - b[1]) >= H * IMG_PAGINA_FRAC:
            inteira, bbox_scan = True, b
            break
    if not inteira and els and _tiras_corpo(els, W, H):
        inteira, bbox_scan = True, (0, 0, W, H)
    if not inteira:                               # detecção nova (e-proc)
        bbox_scan = _bbox_scan_form(page_pike)
        inteira = bbox_scan is not None
    if aproveitavel and not inteira:
        return TipoPagina.NATIVA_DIGITAL, False, None
    if aproveitavel and inteira:
        deficiente = (_densidade_texto(pg_pdfium, texto)
                      < FRAC_TEXTO_MIN_HIBRIDO)
        return TipoPagina.HIBRIDA_COM_OCR, deficiente, bbox_scan
    if len((texto or "").strip()) >= OCR_MIN_CHARS_AVAL:
        return TipoPagina.TEXTO_CORROMPIDO, False, bbox_scan
    return TipoPagina.IMAGEM_SEM_OCR, False, bbox_scan


def decisao_ocr_pagina(page_pike, pg_pdfium, texto: str,
                       reocr_hibrido: str = REOCR_HIBRIDO_PADRAO) -> str:
    """Decisão da pré-passagem de embutir_ocr para UMA página, em texto:
    "pular" | "regioes:N" | "pagina". Espelha exatamente o que embutir_ocr
    faz — usada por tests/regressao/decisoes_ocr.py para garantir que as
    decisões do acervo do SIG nunca mudam (atl.md §9)."""
    tipo, deficiente, _bbox = classificar_pagina(page_pike, pg_pdfium, texto)
    reusa = (tipo is TipoPagina.NATIVA_DIGITAL
             or (tipo is TipoPagina.HIBRIDA_COM_OCR
                 and reocr_hibrido != "sempre"
                 and not (reocr_hibrido == "auto" and deficiente)))
    if reusa or (tipo is TipoPagina.HIBRIDA_COM_OCR
                 and reocr_hibrido != "sempre"):
        els = _elementos(page_pike)
        W, H = _grupo(page_pike)
        cands = [b for kind, _k, b, _ins, rot in (els or [])
                 if kind in ("I", "II") and b and not rot
                 and _imagem_candidata_ocr(b, W, H)]
        if cands:
            return f"regioes:{len(cands)}"
        if reusa:
            return "pular"
        return "regioes:1"     # OCR aditivo da região do scan (e-proc)
    return "pagina"


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


def _imagem_candidata_ocr(bbox, W, H) -> bool:
    """True se a imagem embutida deve receber OCR de região: grande o
    bastante para ter conteúdo (>= IMG_OCR_FRAC_MIN), menor que a página
    escaneada (< IMG_PAGINA_FRAC, já coberta pelo fluxo de página inteira) e
    fora da zona de cabeçalho (logo/timbre). bbox em pontos, origem
    inferior-esquerda."""
    if not W or not H or not bbox:
        return False
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w <= 0 or h <= 0:
        return False
    frac = (w * h) / (W * H)
    if frac < IMG_OCR_FRAC_MIN or frac >= IMG_PAGINA_FRAC:
        return False
    if bbox[1] >= H * (1 - IMG_OCR_ZONA_CABECALHO):
        return False
    return True


def _texto_contido(menor: str, maior: str) -> bool:
    """Comparação TOLERANTE de conteúdo: True se >= OCR_DEDUP_FRAC das
    palavras substantivas (>= 4 letras) de 'menor' aparecem em 'maior'.
    Usada para não duplicar no .md o texto de uma imagem que é apenas a
    versão rasterizada do próprio corpo."""
    pm = set(re.findall(r"\w{4,}", (menor or "").lower()))
    if not pm:
        return False
    pg = set(re.findall(r"\w{4,}", (maior or "").lower()))
    return len(pm & pg) / len(pm) >= OCR_DEDUP_FRAC


def _escala_render(page) -> float:
    """Escala de renderização p/ OCR: OCR_DPI com o cap OCR_MAX_LADO_PX."""
    escala = OCR_DPI / 72.0
    box = page.mediabox
    w_pt = float(box[2]) - float(box[0])
    h_pt = float(box[3]) - float(box[1])
    if max(w_pt, h_pt) * escala > OCR_MAX_LADO_PX:
        escala = OCR_MAX_LADO_PX / max(w_pt, h_pt)
    return escala


def _garantir_fonte(pdf, page, nome: str):
    """Garante a fonte Helvetica 'nome' (ex.: '/FOCR') nos /Resources."""
    res = page.get("/Resources")
    if res is None:
        res = pikepdf.Dictionary()
        page.Resources = res
    fontes = res.get("/Font")
    if fontes is None:
        fontes = pikepdf.Dictionary()
        res.Font = fontes
    if nome not in fontes:
        fontes[nome] = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
            Encoding=pikepdf.Name.WinAnsiEncoding))


def _linhas_texto_ocr(dados, x0, y0, H, sx, sy, dx_px=0.0, dy_px=0.0):
    """Converte o dict do image_to_data em instruções de texto invisível,
    palavra a palavra, com a matemática de alinhamento da v2.3+ (fs pela
    altura da bbox, Tz pela largura real na Helvetica, corte conf >= 40).
    (dx_px, dy_px) deslocam as coordenadas quando 'dados' veio de um RECORTE
    da página renderizada (OCR de imagem embutida); 0,0 = página inteira.
    Retorna (linhas: list[bytes], palavras: list[str], confs: list[int])."""
    linhas, palavras, confs = [], [], []
    for j in range(len(dados["text"])):
        w = _normalizar_ocr((dados["text"][j] or "").strip())
        try:
            conf = int(float(dados["conf"][j]))
        except Exception:
            conf = -1
        if not w or conf < 40:
            continue
        left = dados["left"][j] + dx_px
        top = dados["top"][j] + dy_px
        wpx, hpx = dados["width"][j], dados["height"][j]
        # bbox da palavra em pontos de página (Y do PDF cresce p/ cima)
        x = x0 + left * sx
        base_bbox = y0 + H - (top + hpx) * sy   # fundo da bbox da palavra
        larg_pt = max(wpx * sx, 1.0)
        alt_pt = max(hpx * sy, 4.0)
        # A bbox do Tesseract abrange a altura visível da palavra; numa fonte
        # como a Helvetica as maiúsculas ocupam ~72% do corpo, logo o tamanho
        # de fonte ≈ altura_bbox / 0.72.
        fs = max(alt_pt / 0.72, 4.0)
        # A baseline fica ligeiramente acima do fundo da bbox (descender).
        y = base_bbox + alt_pt * 0.18
        # Escala horizontal: faz a palavra cobrir exatamente larg_pt.
        w_natural = max(_larg_helvetica(w) * fs, 0.1)
        tz = max(1.0, min(1000.0, larg_pt / w_natural * 100.0))
        pal = _escapa_pdf(w.encode("cp1252", errors="replace"))
        linhas.append(
            f"{tz:.1f} Tz /FOCR {fs:.2f} Tf "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ".encode("latin-1")
            + b"(" + pal + b") Tj")
        palavras.append(w)
        confs.append(conf)
    return linhas, palavras, confs


def _pagina_manuscrita_els(els, W, H, existente: str) -> bool:
    """Página majoritariamente MANUSCRITA (best-effort honesto): quase sem
    texto de corpo (< MANUSCRITO_MAX_TEXTO chars) e com imagem(ns) de fração
    >= MANUSCRITO_FRAC_MIN. O OCR roda assim mesmo, mas o Tesseract não lê
    cursiva com fidelidade — o .md marca o bloco como baixa confiança."""
    if len((existente or "").strip()) >= MANUSCRITO_MAX_TEXTO:
        return False
    if els is None:
        return False
    area = (W * H) or 1
    return any(
        kind in ("I", "II") and bbox and not rot
        and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / area >= MANUSCRITO_FRAC_MIN
        for kind, _k, bbox, _i, rot in els)


def _pagina_manuscrita(page, existente: str) -> bool:
    """Compatibilidade: idem _pagina_manuscrita_els, parseando a página."""
    W, H = _grupo(page)
    return _pagina_manuscrita_els(_elementos(page), W, H, existente)


# ---------------- OCR em paralelo por página (v2.9 — O1) ---------------------
# O trabalho pesado (renderizar + pré-processar + Tesseract) é 100% isolável
# por página e não toca em objetos pikepdf (não serializáveis): cada worker
# abre seu próprio handle pypdfium2 do arquivo e devolve o dict do
# image_to_data + geometria. A montagem da camada invisível continua no
# processo PAI. O resultado por página é o mesmo do fluxo sequencial — muda
# só a ordem em que ficam prontos (ex.map preserva a ordem de entrega).
# OMP_THREAD_LIMIT=1 em cada worker: o Tesseract com OpenMP multi-thread é
# mais lento e atrapalharia o paralelismo por processo.

_OCR_W = {}   # estado por worker (handle pypdfium2 aberto preguiçosamente)


def _ocr_workers_auto(pedido=0) -> int:
    """Nº de processos de OCR: o pedido, ou automático com teto por RAM
    (cada worker segura uma imagem de ~15 MP + um motor LSTM)."""
    import os
    if pedido and pedido > 0:
        return int(pedido)
    cpu = os.cpu_count() or 1
    ram_gb = 8.0
    try:
        if os.name == "nt":
            import ctypes

            class _MEM(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _MEM(); m.dwLength = ctypes.sizeof(_MEM)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                ram_gb = m.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass
    return max(1, min(cpu - 1, int(ram_gb // 2)))


def _ocr_worker_init(caminho_pdf, tesseract_cmd, tessdata_prefix):
    """Inicializador de cada processo worker (Windows usa spawn: o estado do
    processo pai — tesseract_cmd, TESSDATA_PREFIX — precisa ser reposto)."""
    import os
    os.environ["OMP_THREAD_LIMIT"] = "1"
    if tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = tessdata_prefix
    if tesseract_cmd:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        except Exception:
            pass
    _OCR_W["caminho"] = caminho_pdf
    _OCR_W["doc"] = None


def _ocr_render_pagina(pag, escala):
    """Render da página p/ OCR; em cinza direto quando OCR_RENDER_CINZA (O3:
    1 byte/pixel em todas as cópias intermediárias em vez de 3)."""
    if OCR_RENDER_CINZA:
        return pag.render(scale=escala, grayscale=True).to_pil()
    return pag.render(scale=escala).to_pil()


def _imagem_em_branco(img_bin) -> bool:
    """True se a imagem binarizada não tem NENHUM pixel de tinta (O4): folha
    separadora/região vazia — nada para o Tesseract ler."""
    try:
        import numpy as np
        return int(np.asarray(img_bin).min()) >= OCR_BRANCO_LIMIAR
    except Exception:
        return False


def _ocr_executar_tarefa(doc, tarefa, lang, cfg_ocr):
    """Executa UMA tarefa de OCR (worker ou inline) e devolve um resultado
    picklável — nada de objetos pikepdf/PIL atravessando processos.

    tarefa: {"idx", "escala", "modo": "pagina"|"regioes",
             "mediabox": (mx0, my0, Wm, Hm), "cands": [bbox, ...]}"""
    import pytesseract
    idx = tarefa["idx"]
    img = _ocr_render_pagina(doc[idx], tarefa["escala"])
    if tarefa["modo"] == "pagina":
        img_ocr = _preparar_imagem_ocr(img)
        if _imagem_em_branco(img_ocr):
            dados = None      # página em branco: pula o Tesseract (O4)
        else:
            dados = pytesseract.image_to_data(
                img_ocr, lang=lang, config=cfg_ocr,
                output_type=pytesseract.Output.DICT)
        return {"idx": idx, "modo": "pagina", "dados": dados,
                "px": (img.width, img.height)}
    # modo "regioes": recorta cada imagem candidata e reconhece só a região
    mx0, my0, Wm, Hm = tarefa["mediabox"]
    sx, sy = Wm / img.width, Hm / img.height
    regs = []
    for bbox in tarefa["cands"]:
        # bbox em pontos (origem inferior-esquerda) -> recorte px (origem sup.)
        cx0 = max(0, int((bbox[0] - mx0) / sx))
        cx1 = min(img.width, int(math.ceil((bbox[2] - mx0) / sx)))
        cy0 = max(0, int((Hm - (bbox[3] - my0)) / sy))
        cy1 = min(img.height, int(math.ceil((Hm - (bbox[1] - my0)) / sy)))
        if cx1 - cx0 < 8 or cy1 - cy0 < 8:
            continue
        rec = _preparar_imagem_ocr(img.crop((cx0, cy0, cx1, cy1)))
        if _imagem_em_branco(rec):
            continue
        try:
            dados = pytesseract.image_to_data(
                rec, lang=lang, config=cfg_ocr,
                output_type=pytesseract.Output.DICT)
        except Exception:
            continue  # erro em uma região só pula aquela região
        regs.append({"dados": dados, "cx0": cx0, "cy0": cy0})
    return {"idx": idx, "modo": "regioes", "regs": regs,
            "px": (img.width, img.height),
            "hibrida": tarefa.get("hibrida", False)}


def _ocr_worker(args):
    """Corpo do worker (nível de módulo: o Windows usa spawn)."""
    tarefa, lang, cfg_ocr = args
    if _OCR_W.get("doc") is None:
        import pypdfium2 as pdfium
        _OCR_W["doc"] = pdfium.PdfDocument(_OCR_W["caminho"])
    return _ocr_executar_tarefa(_OCR_W["doc"], tarefa, lang, cfg_ocr)


def _ocr_camada(pdf, page, linhas_texto):
    """Anexa a camada de texto invisível (Tr 3) com o CTM herdado
    neutralizado (vide _ctm_residual) — a matemática da v2.3+."""
    m_inv = _inverter_matriz(_ctm_residual(page)) or I
    camada = ([b"q",
               ("%.6f %.6f %.6f %.6f %.4f %.4f cm" % m_inv).encode("latin-1"),
               b"BT", b"3 Tr"] + linhas_texto + [b"ET", b"Q"])
    _garantir_fonte(pdf, page, "/FOCR")
    page.contents_add(pdf.make_stream(b"\n".join(camada)), prepend=False)


def embutir_ocr(pdf_path: Path, lang: str, cfg: str, workers: int = None,
                progresso=None, cancelar=None,
                reocr_hibrido: str = REOCR_HIBRIDO_PADRAO):
    """Acrescenta texto invisível de OCR (Text Rendering Mode 3) POR CIMA do
    conteúdo, palavra a palavra, para que o texto fique selecionável e
    pesquisável em qualquer leitor:
      - páginas SEM texto aproveitável: OCR da página inteira (como sempre);
      - páginas COM texto de corpo: OCR por REGIÃO das imagens embutidas
        (prints, documentos anexados — v2.8).

    v2.10: a decisão é do classificador (classificar_pagina, UMA vez por
    página). 'reocr_hibrido' controla as páginas HÍBRIDAS (scan de página
    inteira + camada de texto aproveitável — o caso e-proc/TJSC):
      - "auto" (padrão): reusa a camada quando suficiente; quando DEFICIENTE
        (densidade < FRAC_TEXTO_MIN_HIBRIDO), roda o OCR próprio na região do
        scan SEM remover nada (aditivo — a moldura/camada existente fica);
      - "nunca": sempre reusa a camada existente (avisa se deficiente);
      - "sempre": remove a camada existente e reOCRiza a página inteira
        (lento e pode não melhorar — avisado no main()).

    v2.9 (Tarefa C): o trabalho por página roda em PARALELO num
    ProcessPoolExecutor (vide _ocr_worker; 'workers' = nº de processos,
    None/0 = automático). A montagem da camada invisível continua aqui no
    processo pai (objetos pikepdf não são serializáveis). 'progresso' é um
    callable opcional progresso(etapa, feito, total, detalhe); 'cancelar' é
    um threading.Event opcional — quando setado, interrompe entre páginas
    SEM salvar (o arquivo fica como estava).

    Retorna (n_paginas_ocr, info_ocr). info_ocr é consumido por exportar_md:
    {pagina_0based: {"blocos": [(texto, conf_media)], "manuscrito": bool,
    "origem": str}} — com OCR ligado, TODA página ganha entrada com a
    "origem" do texto (atl.md §8): "texto nativo" / "camada e-proc
    reaproveitada" / "OCR do LIMPAPDF" / "camada e-proc incompleta —
    revisar"."""
    import os
    import pypdfium2 as pdfium
    import pytesseract

    # Garante o motor neural (LSTM, --oem 1) e a segmentação por bloco uniforme
    # de texto (--psm 6), que dá melhor resultado no corpo dos documentos do
    # SIG. Preserva o que já vier em 'cfg' (ex.: --tessdata-dir).
    cfg_ocr = f"{cfg or ''} --oem 1 --psm 6".strip()

    pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    n_ocr = 0
    info = {}
    cancelado = False
    try:
        # ---------- pré-passagem (pai): decide o que cada página precisa ----
        tarefas = []
        existentes = {}
        manuscritos = {}
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            existente = (tp.get_text_range() or "").strip()
            tp.close()
            existentes[i] = existente
            els = _elementos(page)
            W, H = _grupo(page)
            manuscrito = _pagina_manuscrita_els(els, W, H, existente)
            manuscritos[i] = manuscrito
            box = page.mediabox
            mx0, my0 = float(box[0]), float(box[1])
            mediabox = (mx0, my0, float(box[2]) - mx0, float(box[3]) - my0)
            # v2.10: UMA decisão por página (atl.md §5). Para o acervo do SIG
            # os caminhos resultantes são IDÊNTICOS aos da v2.9 (garantido
            # por tests/regressao/decisoes_ocr.py).
            tipo, deficiente, bbox_scan = classificar_pagina(
                page, doc[i], existente)
            reusa = (tipo is TipoPagina.NATIVA_DIGITAL
                     or (tipo is TipoPagina.HIBRIDA_COM_OCR
                         and reocr_hibrido != "sempre"
                         and not (reocr_hibrido == "auto" and deficiente)))
            if reusa:
                if tipo is TipoPagina.NATIVA_DIGITAL:
                    origem = "texto nativo"
                elif deficiente:
                    origem = "camada e-proc incompleta — revisar"
                    print(f"   [hibrido] pag {i + 1}: camada de OCR existente"
                          " parece incompleta — considere --reocr-hibrido"
                          " auto/sempre.", flush=True)
                else:
                    origem = "camada e-proc reaproveitada"
                info[i] = {"blocos": [], "manuscrito": manuscrito,
                           "origem": origem}
                # caminho da v2.8/v2.9: OCR de região das imagens embutidas
                # (prints, anexos) por cima do texto de corpo.
                cands = [bbox for kind, _k, bbox, _ins, rot in (els or [])
                         if kind in ("I", "II") and bbox and not rot
                         and _imagem_candidata_ocr(bbox, W, H)]
                if cands:
                    tarefas.append({"idx": i, "modo": "regioes",
                                    "escala": _escala_render(page),
                                    "mediabox": mediabox, "cands": cands})
                continue
            if tipo is TipoPagina.HIBRIDA_COM_OCR:
                info[i] = {"blocos": [], "manuscrito": manuscrito,
                           "origem": "OCR do LIMPAPDF"}
                if reocr_hibrido == "sempre":
                    # atl.md §7: remove a camada existente e reOCRiza tudo.
                    try:
                        _remover_camada_texto(pdf, page)
                    except Exception as e:
                        print(f"   [aviso] nao removi a camada da pag"
                              f" {i + 1}: {e}")
                    tarefas.append({"idx": i, "modo": "pagina",
                                    "escala": _escala_render(page),
                                    "mediabox": mediabox, "cands": []})
                    continue
                # auto + deficiente: ADITIVO — nada é removido.
                # Se o scan aparece como imagens candidatas VISÍVEIS (corpo
                # fatiado em tiras do SIG), o caminho é o MESMO da v2.9 (OCR
                # de região das candidatas) — decisão idêntica, regressão
                # garantida. O caminho novo (região do scan detectado no
                # Form XObject) só entra quando NÃO há candidatas visíveis:
                # o arranjo do e-proc, invisível para _elementos.
                cands = [bbox for kind, _k, bbox, _ins, rot in (els or [])
                         if kind in ("I", "II") and bbox and not rot
                         and _imagem_candidata_ocr(bbox, W, H)]
                if cands:
                    tarefas.append({"idx": i, "modo": "regioes",
                                    "escala": _escala_render(page),
                                    "mediabox": mediabox, "cands": cands})
                else:
                    print(f"   [hibrido] pag {i + 1}: camada existente"
                          " incompleta; OCR proprio da regiao do scan.",
                          flush=True)
                    tarefas.append({"idx": i, "modo": "regioes",
                                    "escala": _escala_render(page),
                                    "mediabox": mediabox,
                                    "cands": [bbox_scan], "hibrida": True})
                continue
            # TEXTO_CORROMPIDO / IMAGEM_SEM_OCR: OCR de página inteira,
            # removendo antes a camada podre (fonte sem /ToUnicode), senão a
            # extração continuaria pegando o lixo em vez do texto do OCR.
            info[i] = {"blocos": [], "manuscrito": manuscrito,
                       "origem": "OCR do LIMPAPDF"}
            if tipo is TipoPagina.TEXTO_CORROMPIDO:
                try:
                    if _remover_camada_texto(pdf, page):
                        print(f"   Pag {i + 1}: camada de texto corrompida"
                              " removida; aplicando OCR.", flush=True)
                except Exception as e:
                    print(f"   [aviso] nao removi a camada podre da pag"
                          f" {i + 1}: {e}")
            tarefas.append({"idx": i, "modo": "pagina",
                            "escala": _escala_render(page),
                            "mediabox": mediabox, "cands": []})
        if not tarefas:
            return 0, info

        # ---------- execução (workers) + montagem (pai) ---------------------
        def montar(r):
            nonlocal n_ocr
            i = r["idx"]
            page = pdf.pages[i]
            box = page.mediabox
            mx0, my0 = float(box[0]), float(box[1])
            Wm, Hm = float(box[2]) - mx0, float(box[3]) - my0
            sx, sy = Wm / r["px"][0], Hm / r["px"][1]
            if r["modo"] == "pagina":
                if r["dados"] is None:
                    return  # página em branco (O4)
                print(f"   OCR pagina {i + 1}...", flush=True)
                corpo, _pals, _confs = _linhas_texto_ocr(
                    r["dados"], mx0, my0, Hm, sx, sy)
                if not corpo:
                    return
                _ocr_camada(pdf, page, corpo)
                n_ocr += 1
                return
            # regiões de imagem embutida (ou do scan da página híbrida)
            linhas_pag, blocos = [], []
            for reg in r["regs"]:
                linhas, palavras, confs = _linhas_texto_ocr(
                    reg["dados"], mx0, my0, Hm, sx, sy,
                    dx_px=reg["cx0"], dy_px=reg["cy0"])
                texto = " ".join(palavras).strip()
                if not texto:
                    continue
                if _texto_contido(texto, existentes[i]):
                    continue  # já está no corpo: não duplica (nem embute)
                linhas_pag += linhas
                blocos.append((texto, sum(confs) / len(confs)))
            if linhas_pag:
                _ocr_camada(pdf, page, linhas_pag)
            if r.get("hibrida"):
                # página híbrida deficiente (v2.10): o texto do OCR fica só
                # na camada invisível (sai no corpo do .md pela extração) —
                # sem blocos de citação; a origem já foi registrada.
                if linhas_pag:
                    print(f"   OCR do scan da pagina hibrida {i + 1}...",
                          flush=True)
                    n_ocr += 1
                return
            if blocos:
                print(f"   OCR de imagem embutida na pagina {i + 1}"
                      f" ({len(blocos)} bloco(s))...", flush=True)
                n_ocr += 1
            if blocos or manuscritos[i]:
                info.setdefault(i, {}).update(
                    {"blocos": blocos, "manuscrito": manuscritos[i]})

        n_workers = _ocr_workers_auto(
            workers if workers is not None and workers > 0 else OCR_WORKERS)
        feitas = 0
        if n_workers > 1 and len(tarefas) > 1:
            from concurrent.futures import ProcessPoolExecutor
            exe = ProcessPoolExecutor(
                max_workers=min(n_workers, len(tarefas)),
                initializer=_ocr_worker_init,
                initargs=(str(pdf_path),
                          getattr(pytesseract.pytesseract, "tesseract_cmd",
                                  None),
                          os.environ.get("TESSDATA_PREFIX")))
            try:
                for r in exe.map(_ocr_worker,
                                 [(t, lang, cfg_ocr) for t in tarefas]):
                    if cancelar is not None and cancelar.is_set():
                        cancelado = True
                        break
                    montar(r)
                    feitas += 1
                    if progresso:
                        progresso("ocr", feitas, len(tarefas),
                                  f"página {r['idx'] + 1}")
            finally:
                exe.shutdown(wait=True, cancel_futures=True)
        else:
            for t in tarefas:
                if cancelar is not None and cancelar.is_set():
                    cancelado = True
                    break
                r = _ocr_executar_tarefa(doc, t, lang, cfg_ocr)
                montar(r)
                feitas += 1
                if progresso:
                    progresso("ocr", feitas, len(tarefas),
                              f"página {t['idx'] + 1}")

        if n_ocr and not cancelado:
            doc.close()
            doc = None
            pdf.save(pdf_path)
    finally:
        if doc is not None:
            doc.close()
        pdf.close()
    return n_ocr, info


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


def numerar_paginas(pdf_path: Path, total: int, inicio: int = 1,
                    progresso=None, cancelar=None) -> int:
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
        n_pag = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            if cancelar is not None and cancelar.is_set():
                return 0   # sem save: o arquivo fica como estava
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
            _garantir_fonte(pdf, page, "/FNUM")
            page.contents_add(pdf.make_stream(b"\n".join(linhas)),
                              prepend=False)
            n_num += 1
            if progresso:
                progresso("numeracao", i + 1, n_pag, f"página {num}")
        pdf.save(pdf_path)
    return n_num


def _salvar_bloco(pdf, ini: int, fim: int, destino: Path) -> int:
    """Grava as páginas [ini, fim) num novo PDF e devolve o tamanho REAL em
    bytes do arquivo salvo (mesma compressão do fluxo normal)."""
    novo = pikepdf.new()
    for p in pdf.pages[ini:fim]:
        novo.pages.append(p)
    novo.save(destino, compress_streams=True,
              object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return destino.stat().st_size


def dividir_pdf(caminho: Path, max_mb: float, progresso=None, cancelar=None):
    """Divide o PDF em partes de até 'max_mb' MB (tamanho REAL do arquivo).

    Estratégia CRESCER-GRAVAR-MEDIR: o bloco cresce página a página e, a cada
    candidata, é GRAVADO em disco e MEDIDO — nada de estimar MB/página (o
    peso de uma página NÃO é linear: uma escaneada/com prints pesa muitas
    vezes mais que uma só-texto, e estimativas por stream subestimam o
    arquivo final em 6-34%). Se a página candidata estoura o limite, ela NÃO
    entra e vira o início da próxima parte. REGRA INVIOLÁVEL: nenhuma página
    é perdida nem fracionada — uma página que sozinha excede o limite sai
    numa parte própria, com aviso.

    Retorna [(arquivo, offset)], offset = nº (1-based) da 1ª página da parte
    no documento inteiro (numeração contínua no .md). O original é
    substituído pelas partes. max_mb <= 0 = não dividir."""
    if not max_mb or max_mb <= 0:
        return [(caminho, 1)]
    limite = int(max_mb * 1024 * 1024 * DIV_MARGEM_SEGURANCA)
    if caminho.stat().st_size <= limite:
        return [(caminho, 1)]
    tmp = caminho.with_name(caminho.stem + "_divisao_tmp.pdf")
    partes = []
    try:
        with pikepdf.open(caminho) as pdf:
            n = len(pdf.pages)
            i, k = 0, 0
            while i < n:
                if cancelar is not None and cancelar.is_set():
                    # aborta a divisão INTEIRA: apaga as partes já gravadas e
                    # devolve o arquivo original intacto (nada pela metade)
                    for p, _off in partes:
                        try:
                            p.unlink()
                        except OSError:
                            pass
                    return [(caminho, 1)]
                k += 1
                fim = i + 1
                tam = _salvar_bloco(pdf, i, fim, tmp)
                if tam > limite:
                    print(f"   [aviso] Pagina {i + 1} sozinha tem"
                          f" {tam / 1048576.0:.1f} MB (acima do limite de"
                          f" {max_mb:g} MB); mantida inteira para nao perder"
                          " conteudo.")
                else:
                    # cresce enquanto o arquivo salvo couber no limite
                    while fim < n and _salvar_bloco(pdf, i, fim + 1, tmp) <= limite:
                        fim += 1
                    if fim < n:
                        _salvar_bloco(pdf, i, fim, tmp)  # regrava o aprovado
                destino = caminho.with_name(f"{caminho.stem}_parte{k:02d}.pdf")
                tmp.replace(destino)
                partes.append((destino, i + 1))  # offset = 1ª página da parte
                i = fim
                if progresso:
                    progresso("divisao", i, n, f"parte {k}")
    finally:
        if tmp.exists():
            tmp.unlink()
    if len(partes) == 1:
        # coube tudo numa parte (ex.: recompressão reduziu, ou página única
        # gigante): mantém o nome original, sem sufixo _parte01
        partes[0][0].replace(caminho)
        return [(caminho, 1)]
    caminho.unlink()
    print(f"   Dividido em {len(partes)} partes de ate {max_mb:g} MB.")
    return partes


# ---------------- planejamento p/ barra de progresso (v2.9/B) ---------------
# Pesos em "unidades de trabalho" POR PÁGINA, calibrados pelos tempos MEDIDOS
# do perfil (PERFIL_ANTES/DEPOIS.md, s/página no acervo de referência), para
# que a barra seja aproximadamente linear no TEMPO real — é o que o usuário
# percebe como "barra honesta". P_OCR domina, como esperado.
P_LIMPEZA = 1.0     # limpeza estrutural (análise + reescrita): ~0,5 s/pág
P_OCR = 2.6         # página de OCR com paralelismo automático: ~1,3 s/pág
P_NUMERA = 0.2      # carimbo de paginação: ~0,09 s/pág
P_EXPORT = 0.4      # exportação .md (pós-O5): ~0,2 s/pág
P_DIVIDE = 0.2      # divisão (crescer-gravar-medir), por página gravada


def planejar(arquivos, com_ocr: bool = True, progresso=None):
    """Pré-passagem de planejamento (Tarefa B): para cada PDF, conta as
    páginas e QUANTAS realmente irão para o OCR de página inteira
    (_texto_e_aproveitavel num varrimento rápido de get_textpage — ms/página).
    Devolve uma lista de dicts {"arquivo", "paginas", "paginas_ocr",
    "unidades"} — um ORÇAMENTO exato de unidades de trabalho, não estimativa
    por arquivo. Nunca quebra: erro num arquivo vira orçamento aproximado."""
    import pypdfium2 as pdfium
    plano = []
    for k, arq in enumerate(arquivos):
        n = n_ocr = 0
        try:
            doc = pdfium.PdfDocument(str(arq))
            try:
                n = len(doc)
                for i in range(n):
                    tp = doc[i].get_textpage()
                    t = tp.get_text_range() or ""
                    tp.close()
                    if not _texto_e_aproveitavel(t):
                        n_ocr += 1
            finally:
                doc.close()
        except Exception:
            n = max(n, 1)
            n_ocr = n
        unidades = (n * (P_LIMPEZA + P_NUMERA + P_EXPORT + P_DIVIDE)
                    + (n_ocr * P_OCR if com_ocr else 0))
        plano.append({"arquivo": Path(arq), "paginas": n,
                      "paginas_ocr": n_ocr, "unidades": unidades})
        if progresso:
            progresso("planejamento", k + 1, len(arquivos), Path(arq).name)
    return plano


# ------------------------------- CLI ----------------------------------------

def limpa_pdf(origem: Path, destino: Path, sem_cabecalho: bool,
              progresso=None, cancelar=None) -> int:
    """Limpeza estrutural. 'progresso'/'cancelar' (v2.9/B): callback opcional
    de progresso e threading.Event de cancelamento — cancelado ANTES do save,
    o destino não é gravado (nunca fica PDF pela metade)."""
    n_alt = 0
    n_prot = 0
    with pikepdf.open(origem) as pdf:
        n_pag = len(pdf.pages)
        if sem_cabecalho:
            boiler, boiler_base_P, cortes, faixas_base = analisar(
                pdf, progresso=progresso)
        else:
            boiler, boiler_base_P, cortes, faixas_base = set(), set(), {}, {}
        for idx, page in enumerate(pdf.pages):
            if cancelar is not None and cancelar.is_set():
                return n_alt   # sem save: o original fica intocado
            alterado, protegido = reescrever(
                pdf, page, idx, boiler, boiler_base_P, cortes, faixas_base,
                sem_cabecalho)
            if alterado:
                n_alt += 1
            if protegido:
                n_prot += 1
            if progresso:
                progresso("limpeza", idx + 1, n_pag, f"página {idx + 1}")
        pdf.save(destino, compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    if n_prot:
        print(f"   [protecao] {n_prot} pagina(s) mantida(s) intacta(s) por"
              " remocao excessiva (rede de seguranca).", flush=True)
    return n_alt


def main():
    # OBRIGATÓRIO antes de qualquer coisa: sem isto, o executável congelado
    # (PyInstaller) entra em "fork bomb" no Windows quando o OCR paralelo
    # cria os processos worker (o spawn reexecuta o exe).
    import multiprocessing
    multiprocessing.freeze_support()

    ap = argparse.ArgumentParser(description="Limpa PDFs do SIG MPSC (v2)")
    ap.add_argument("entrada", help="Arquivo PDF ou pasta com PDFs")
    ap.add_argument("--saida", help="Pasta de saída (padrão: sufixo _limpo)")
    ap.add_argument("--sem-cabecalho", action="store_true",
                    help="Remove cabeçalho/rodapé (texto, logos e linhas)")
    ap.add_argument("--md", "--txt", dest="md", action="store_true",
                    help="Exporta o conteúdo em Markdown (.md) estruturado"
                         " para colar na IA (--txt é alias antigo)")
    ap.add_argument("--ocr", action="store_true",
                    help="OCR nas páginas sem camada de texto (requer Tesseract):"
                         " o texto fica selecionável no PDF e entra no .txt")
    ap.add_argument("--max-mb", type=float, default=MAX_MB_PARTE,
                    help=f"divide o PDF em partes de até N megabytes (padrão"
                         f" {MAX_MB_PARTE} MB; use 0 para não dividir)")
    ap.add_argument("--sem-numero", action="store_true",
                    help="NÃO carimba o número da página no canto superior"
                         " direito (por padrão a paginação contínua é"
                         " aplicada para facilitar a referência por IA)")
    ap.add_argument("--workers", type=int, default=0,
                    help="nº de processos de OCR em paralelo (0 = automático:"
                         " núcleos-1 com teto por RAM; 1 = sequencial)")
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
        info_ocr = {}
        if lang:
            try:
                n_ocr, info_ocr = embutir_ocr(destino, lang, cfg,
                                              workers=args.workers)
                if n_ocr:
                    print(f"   OCR embutido em {n_ocr} páginas (texto"
                          " selecionável).")
            except Exception as e:
                print(f"   [aviso] OCR falhou: {e}")
        # Total de páginas do documento limpo (já com OCR): usado tanto pela
        # paginação carimbada quanto pelo "## Página N de TOTAL" do .md.
        total_pag = 0
        try:
            with pikepdf.open(destino) as _p:
                total_pag = len(_p.pages)
        except Exception:
            pass
        # Paginação CONTÍNUA: carimba os números ANTES de dividir, sobre o PDF
        # inteiro, para que a contagem vá de 1 ao total sem reiniciar a cada
        # parte.
        if not args.sem_numero and total_pag:
            try:
                numerar_paginas(destino, total_pag, inicio=1)
                print(f"   Paginas numeradas (1 a {total_pag}) no canto"
                      " superior direito.")
            except Exception as e:
                print(f"   [aviso] numeração de páginas falhou: {e}")
        try:
            partes = dividir_pdf(destino, args.max_mb)
        except Exception as e:
            print(f"   [aviso] não consegui dividir ({e}); arquivo único.")
            partes = [(destino, 1)]
        nomes = []
        for parte, offset in partes:
            nomes.append(parte.name)
            if args.md:
                md = parte.with_suffix(".md")
                try:
                    exportar_md(parte, md, offset=offset, total=total_pag,
                                info_ocr=info_ocr)
                    if md.is_file():
                        nomes.append(md.name)
                except Exception as e:
                    print(f"   [aviso] falha ao gerar {md.name}: {e}")
        print(f"[OK] {arq.name} -> {', '.join(nomes)} ({n} páginas alteradas)")


if __name__ == "__main__":
    main()
