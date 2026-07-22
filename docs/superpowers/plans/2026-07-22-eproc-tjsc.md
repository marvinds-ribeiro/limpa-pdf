# Suporte a PDFs do e-proc/TJSC — Plano de Implementação (v2.10)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classificador explícito de tipo de página (4 classes) + verificação de
suficiência da camada de texto + flag `--reocr-hibrido`, para que PDFs do
e-proc/TJSC com scan sem OCR de corpo (caso `ex1.pdf`) sejam recuperados pelo
OCR próprio — **sem alterar nenhuma decisão nos arquivos do SIG**.

**Architecture:** Tudo em `limpa_pdf_mpsc.py` (base única, convenção do
projeto). O classificador é uma pré-passagem por página em `embutir_ocr()`
(uma decisão por página, repassada a `exportar_md` via `info_ocr`). A detecção
de imagem de página inteira ganha um caminho NOVO consciente de Form XObject,
usado SÓ pelo classificador — a lógica de limpeza (`_iter_elementos`,
`_motivo_bruto`) não muda.

**Tech Stack:** pikepdf, pypdfium2, pytesseract, Pillow (já no projeto).

## Fatos medidos (RELATORIO_EPROC.md — base de toda calibragem)

- `ex1.pdf` (34 págs): 31 páginas híbridas (scan 1656×2339 dentro de Form
  XObject `/TPLn`) + 3 nativas (1, 31, 32). **Não há OCR de corpo** — o texto
  extraível das híbridas (~264 chars) é só a moldura e-proc/SGP-e.
- Densidade (chars por 1000 px de tinta, render 72 dpi, limiar 128): nativas
  boas **54,6–65,5**; híbridas só-moldura **1,3–40,6**. Vão entre 40,6 e 54,6
  → `FRAC_TEXTO_MIN_HIBRIDO = 45.0`.
- `_iter_elementos` NÃO desce em Form XObjects e o ramo `Do` de imagem compara
  `sub == "\Image"` (barra invertida — nunca casa; latente desde o commit
  inicial). Não corrigir esse ramo neste plano (superfície do SIG); detecção
  nova e separada para o classificador.
- Área de scan dentro de form: imagem ≥ 300 000 px (`ex1`: 3,9 Mpx; logos/QR
  ordens de grandeza abaixo).
- Saída atual sobre `ex1`: 31 páginas sem corpo no `.md`; páginas de separação
  1 e 32 saem em branco (bug distinto, Task 7 investiga).
- Originais do SIG p/ regressão: `C:\Users\User\Desktop\PDFs para Teste\exemplos\`
  (10 PDFs; `exemplos/` do repo é git-ignored e hoje só tem os `ex1*`).

## Global Constraints

- 100% local/offline; nenhuma dependência de rede em tempo de uso.
- **Zero mudança de decisão nos arquivos do SIG** (portão: Task 1 baseline →
  Task 8 comparação; falha = bloqueia).
- Qualidade de OCR inegociável; pipeline de OCR atual (400 dpi, Otsu,
  `--oem 1 --psm 6`, CTM residual) intocado.
- Camada existente NUNCA é destruída no modo `auto` (aditivo); só o modo
  `sempre` remove (com aviso), como especifica o prompt.
- Constantes nomeadas no topo do módulo com comentário; comentários em PT.
- Versão v2.10 no docstring com changelog no estilo das anteriores.
- Assinaturas públicas (GUI!) só ganham parâmetros com default —
  `embutir_ocr(..., reocr_hibrido=REOCR_HIBRIDO_PADRAO)`.
- Commits frequentes; branch `eproc-v2.10`; NADA merge em master sem revisão
  do usuário (regra 4 do atl.md).

---

### Task 1: Restaurar exemplos do SIG + baselines ANTES de qualquer mudança

**Files:**
- Modify: `tests/regressao/verificar_regressao.py:146` (filtro "limpo")
- Create: `tests/regressao/decisoes_ocr.py`
- Create: `tests/regressao/decisoes_baseline.json` (gerado)

**Interfaces:**
- Produces: `decisoes_ocr.py --baseline` / modo comparação (exit 1 em
  divergência); `decidir_paginas(pdf_path) -> dict[str, str]` com a decisão
  textual por página (`"pular"`, `"pagina"`, `"regioes:N"`).

- [ ] **Step 1: copiar os originais do SIG de volta** (pasta é git-ignored):

```powershell
Copy-Item "C:\Users\User\Desktop\PDFs para Teste\exemplos\*.pdf" exemplos\ -Exclude "*LIMPO*"
```

- [ ] **Step 2: excluir saídas limpas do coletor por nome, caso-insensível**
  (hoje `"LIMPO" not in p.stem` deixaria passar `ex1 limpo.pdf` como entrada):

```python
# verificar_regressao.py, em coletar():
    pdfs = [p for p in sorted(EXEMPLOS.glob("*.pdf"))
            if "limpo" not in p.stem.lower()]
```

- [ ] **Step 3: criar `tests/regressao/decisoes_ocr.py`** — replica a
  pré-passagem de `embutir_ocr` (sem rodar OCR) e grava a decisão por página:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decisoes_ocr.py — baseline das DECISÕES de OCR por página (atl.md §9).

--baseline grava decisoes_baseline.json; sem flag, compara e FALHA (exit 1)
se qualquer decisão de um arquivo do SIG mudou. ex1.pdf entra no baseline,
mas mudanças nele são reportadas como [mudanca esperada] (não falham) até o
classificador entrar; depois o baseline é regravado."""
import argparse, json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import pikepdf
import pypdfium2 as pdfium
import limpa_pdf_mpsc as nucleo

EXEMPLOS = RAIZ / "exemplos"
BASELINE = Path(__file__).parent / "decisoes_baseline.json"
SIG = {f"exemplo{n}.pdf" for n in range(2, 10)} | {"exemplo 1.pdf",
                                                   "Apagou demais ORIGINAL.pdf"}

def decidir_paginas(pdf_path: Path) -> dict:
    """Decisão da pré-passagem de embutir_ocr, POR página, sem rodar OCR."""
    out = {}
    pdf = pikepdf.open(pdf_path)
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            existente = (tp.get_text_range() or "").strip()
            tp.close()
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
        pdf.close(); doc.close()
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()
    atual = {p.name: decidir_paginas(p)
             for p in sorted(EXEMPLOS.glob("*.pdf"))
             if "limpo" not in p.stem.lower()}
    if args.baseline:
        BASELINE.write_text(json.dumps(atual, indent=1), encoding="utf-8")
        print(f"Baseline de decisoes gravado em {BASELINE}")
        return
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    falhas = []
    for nome, pags in base.items():
        for pag, dec in pags.items():
            nova = atual.get(nome, {}).get(pag)
            if nova != dec:
                msg = f"{nome} pag {int(pag)+1}: {dec} -> {nova}"
                if nome in SIG:
                    falhas.append(msg)
                else:
                    print(f"[mudanca esperada] {msg}")
    if falhas:
        for f in falhas:
            print(f"[FALHA SIG] {f}")
        sys.exit(1)
    print("OK: decisoes do SIG identicas ao baseline.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: gerar os DOIS baselines com o código atual (pré-mudança):**

```powershell
python tests/regressao/decisoes_ocr.py --baseline
python tests/regressao/verificar_regressao.py --baseline   # regrava com ex1 incluso
python tests/regressao/decisoes_ocr.py    # deve passar trivialmente
python tests/regressao/verificar_regressao.py   # idem
```

- [ ] **Step 5: commit** (`test: baseline de decisões de OCR + exemplos SIG restaurados`).

---

### Task 2: Classificador de página (código novo, aditivo)

**Files:**
- Modify: `limpa_pdf_mpsc.py` (novas constantes + funções, perto de
  `_texto_e_aproveitavel`, ~linha 1755)
- Test: `tests/test_classificador.py`

**Interfaces:**
- Produces:
  - `class TipoPagina(Enum): NATIVA_DIGITAL, HIBRIDA_COM_OCR, IMAGEM_SEM_OCR, TEXTO_CORROMPIDO`
  - `classificar_pagina(page_pike, pg_pdfium, texto: str) -> tuple[TipoPagina, bool, tuple|None]`
    → `(tipo, camada_deficiente, bbox_scan)`; `bbox_scan` = colocação do
    form/imagem de página inteira em pontos de página (p/ OCR de região), ou
    `None`.
  - Constantes: `FRAC_TEXTO_MIN_HIBRIDO = 45.0`, `CLAS_RENDER_ESCALA = 1.0`,
    `CLAS_LIMIAR_TINTA = 128`, `CLAS_MIN_PX_SCAN = 300_000`,
    `REOCR_HIBRIDO_PADRAO = "auto"`.

- [ ] **Step 1: testes que falham** (usam `exemplos/ex1.pdf` e um SIG):

```python
# tests/test_classificador.py
import sys
from pathlib import Path
import pikepdf
import pypdfium2 as pdfium
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import limpa_pdf_mpsc as nucleo

EX1 = RAIZ / "exemplos" / "ex1.pdf"
SIG1 = RAIZ / "exemplos" / "exemplo 1.pdf"

def _classificar(caminho, i):
    pdf = pikepdf.open(caminho)
    doc = pdfium.PdfDocument(str(caminho))
    try:
        tp = doc[i].get_textpage()
        texto = (tp.get_text_range() or "").strip()
        tp.close()
        return nucleo.classificar_pagina(pdf.pages[i], doc[i], texto)
    finally:
        pdf.close(); doc.close()

@pytest.mark.skipif(not EX1.exists(), reason="ex1.pdf ausente")
class TestEx1:
    def test_pagina_separacao_e_nativa(self):
        tipo, deficiente, bbox = _classificar(EX1, 0)
        assert tipo is nucleo.TipoPagina.NATIVA_DIGITAL
        assert not deficiente and bbox is None

    def test_scan_com_moldura_e_hibrida_deficiente(self):
        tipo, deficiente, bbox = _classificar(EX1, 1)   # pag 2: dens 21,8
        assert tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR
        assert deficiente and bbox is not None

    def test_scan_quase_em_branco_nao_e_deficiente(self):
        tipo, deficiente, _ = _classificar(EX1, 22)     # pag 23: dens 63,8
        assert tipo is nucleo.TipoPagina.HIBRIDA_COM_OCR
        assert not deficiente

    def test_pagina_assinaturas_e_nativa(self):
        tipo, _, _ = _classificar(EX1, 30)              # pag 31
        assert tipo is nucleo.TipoPagina.NATIVA_DIGITAL

@pytest.mark.skipif(not SIG1.exists(), reason="exemplo 1.pdf ausente")
def test_sig_nativo_nunca_deficiente():
    # Nenhuma página de SIG nativo pode virar 'deficiente' (regra §6 do
    # prompt: a verificação de densidade não altera decisões do SIG).
    doc = pdfium.PdfDocument(str(SIG1))
    pdf = pikepdf.open(SIG1)
    try:
        for i, page in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            texto = (tp.get_text_range() or "").strip()
            tp.close()
            tipo, deficiente, _ = nucleo.classificar_pagina(page, doc[i], texto)
            if tipo is nucleo.TipoPagina.NATIVA_DIGITAL:
                assert not deficiente
    finally:
        pdf.close(); doc.close()
```

- [ ] **Step 2: rodar e ver falhar** (`pytest tests/test_classificador.py -v`
  → `AttributeError: ... TipoPagina`).

- [ ] **Step 3: implementar em `limpa_pdf_mpsc.py`.** Constantes (topo do
  bloco de OCR, após `MANUSCRITO_FRAC_MIN`):

```python
# --- Classificador de tipo de página (v2.10, e-proc/TJSC) --------------------
# O e-proc desenha o scan DENTRO de um Form XObject (Do de /TPLn) que
# _iter_elementos não enxerga; a detecção abaixo é usada SÓ pelo
# classificador — a lógica de limpeza não muda (regressão do SIG).
CLAS_RENDER_ESCALA = 1.0    # render p/ medir tinta: 1.0 = 72 dpi (ms/página)
CLAS_LIMIAR_TINTA = 128     # pixel < isso (cinza 0-255) = "tinta"
CLAS_MIN_PX_SCAN = 300_000  # imagem com >= isso px dentro de form = scan
                            # (ex1: 3,9 Mpx; logos/QR ficam ordens abaixo)
# Densidade mínima (chars extraídos por 1000 px de tinta a 72 dpi) para a
# camada de uma página HÍBRIDA ser SUFICIENTE. Medido em ex1.pdf
# (RELATORIO_EPROC.md): nativas boas 54,6-65,5; híbridas só-moldura 1,3-40,6.
FRAC_TEXTO_MIN_HIBRIDO = 45.0
# Política padrão p/ páginas híbridas: "auto" reusa a camada boa e roda OCR
# próprio só nas deficientes; "nunca" sempre reusa; "sempre" força reOCR.
REOCR_HIBRIDO_PADRAO = "auto"
```

  Funções (adaptar de `diag_eproc.py`, que já as validou em `ex1.pdf`):

```python
class TipoPagina(Enum):          # import enum no topo do módulo
    NATIVA_DIGITAL = "nativa"          # texto real, sem imagem de página
    HIBRIDA_COM_OCR = "hibrida"        # imagem de página + camada aproveitável
    IMAGEM_SEM_OCR = "imagem"          # imagem sem camada (OCR próprio)
    TEXTO_CORROMPIDO = "corrompida"    # camada é lixo (remove + OCR)


def _form_tem_imagem_grande(xo, nivel=0):
    # (idem diag_eproc.py: desce até 3 níveis; True se contém /Image com
    #  Width*Height >= CLAS_MIN_PX_SCAN)

def _bbox_scan_form(page):
    """Rastreia o CTM no stream DE PÁGINA; para cada Do de Form com imagem
    grande dentro, devolve o bbox da colocação do /BBox (com /Matrix) se
    cobrir >= IMG_PAGINA_FRAC da largura E altura; senão None.
    (idem _forms_pagina_inteira do diag_eproc.py, devolvendo o bbox)"""

def _densidade_texto(pg_pdfium, texto):
    """chars não-brancos por 1000 px de tinta (render CLAS_RENDER_ESCALA,
    limiar CLAS_LIMIAR_TINTA). Sem tinta -> densidade infinita (nunca
    deficiente)."""

def classificar_pagina(page_pike, pg_pdfium, texto):
    """UMA decisão por página (atl.md §5). Devolve (TipoPagina,
    camada_deficiente, bbox_scan). camada_deficiente só pode ser True para
    HIBRIDA_COM_OCR — nativas do SIG jamais são afetadas (§6)."""
    aproveitavel = _texto_e_aproveitavel(texto)
    bbox_scan = None
    els = _elementos(page_pike)
    W, H = _grupo(page_pike)
    inteira = False
    for kind, _k, b, _i, rot in (els or []):        # detecção viva (SIG)
        if kind in ("I", "II") and b and not rot \
                and (b[2] - b[0]) >= W * IMG_PAGINA_FRAC \
                and (b[3] - b[1]) >= H * IMG_PAGINA_FRAC:
            inteira, bbox_scan = True, b
            break
    if not inteira and els and _tiras_corpo(els, W, H):
        inteira, bbox_scan = True, (0, 0, W, H)
    if not inteira:                                  # detecção nova (e-proc)
        bbox_scan = _bbox_scan_form(page_pike)
        inteira = bbox_scan is not None
    if aproveitavel and not inteira:
        return TipoPagina.NATIVA_DIGITAL, False, None
    if aproveitavel and inteira:
        deficiente = _densidade_texto(pg_pdfium, texto) < FRAC_TEXTO_MIN_HIBRIDO
        return TipoPagina.HIBRIDA_COM_OCR, deficiente, bbox_scan
    if len((texto or "").strip()) >= OCR_MIN_CHARS_AVAL:
        return TipoPagina.TEXTO_CORROMPIDO, False, bbox_scan
    return TipoPagina.IMAGEM_SEM_OCR, False, bbox_scan
```

- [ ] **Step 4: rodar até passar** (`pytest tests/test_classificador.py -v`).
- [ ] **Step 5: regressões de decisão** (nada pode mudar — o classificador
  ainda não está ligado): `python tests/regressao/decisoes_ocr.py`.
- [ ] **Step 6: commit** (`feat: classificar_pagina (4 tipos) + detecção de scan em Form XObject`).

---

### Task 3: Integrar o classificador a `embutir_ocr` + flag `reocr_hibrido`

**Files:**
- Modify: `limpa_pdf_mpsc.py:2107-2190` (pré-passagem de `embutir_ocr`)
- Test: `tests/test_classificador.py` (novo teste de integração)

**Interfaces:**
- Consumes: `classificar_pagina` (Task 2).
- Produces: `embutir_ocr(pdf_path, lang, cfg, workers=None, progresso=None,
  cancelar=None, reocr_hibrido=REOCR_HIBRIDO_PADRAO)`; `info_ocr[i]` ganha a
  chave `"origem"` com um de: `"texto nativo"`, `"camada e-proc
  reaproveitada"`, `"OCR do LIMPAPDF"`, `"camada e-proc incompleta —
  revisar"` (consumida na Task 4).

- [ ] **Step 1: teste de integração que falha** (roda `embutir_ocr` numa
  CÓPIA de `ex1.pdf` com `reocr_hibrido="auto"`; requer Tesseract — marcar
  `@pytest.mark.skipif` se `_preparar_ocr()` falhar):

```python
def test_embutir_ocr_recupera_hibrida_deficiente(tmp_path):
    try:
        lang, cfg = nucleo._preparar_ocr()
    except Exception:
        pytest.skip("Tesseract indisponivel")
    alvo = tmp_path / "ex1.pdf"
    shutil.copy(EX1, alvo)
    n, info = nucleo.embutir_ocr(alvo, lang, cfg, workers=1,
                                 reocr_hibrido="auto")
    assert n > 0                      # antes: 0 páginas de OCR em ex1
    # pag 2 (0-based 1) era deficiente: precisa ter ganhado OCR e origem
    assert info[1]["origem"].startswith("camada e-proc incompleta")
    doc = pdfium.PdfDocument(str(alvo))
    tp = doc[1].get_textpage(); t = tp.get_text_range() or ""
    tp.close(); doc.close()
    assert len(t.strip()) > 400       # moldura (264) + corpo OCR
    assert "Evento 1" in t            # moldura preservada (aditivo!)
```

- [ ] **Step 2: implementar a integração.** Na pré-passagem
  (`limpa_pdf_mpsc.py:2146-2186`), substituir o teste
  `if _texto_e_aproveitavel(existente):` pela decisão única:

```python
            tipo, deficiente, bbox_scan = classificar_pagina(
                page, doc[i], existente)
            reusa = tipo is TipoPagina.NATIVA_DIGITAL or (
                tipo is TipoPagina.HIBRIDA_COM_OCR and (
                    reocr_hibrido == "nunca"
                    or (reocr_hibrido == "auto" and not deficiente)))
            if tipo is TipoPagina.HIBRIDA_COM_OCR and reocr_hibrido == "sempre":
                reusa = False
            if reusa:
                # caminho ATUAL intocado (regioes de imagens embutidas,
                # manuscrito) — para o SIG nada muda.
                origem = ("texto nativo"
                          if tipo is TipoPagina.NATIVA_DIGITAL
                          else "camada e-proc reaproveitada")
                if tipo is TipoPagina.HIBRIDA_COM_OCR and deficiente:
                    origem = "camada e-proc incompleta — revisar"
                    print(f"   [hibrido] pag {i + 1}: camada de OCR existente"
                          " parece incompleta — considere --reocr-hibrido"
                          " (auto/sempre).", flush=True)
                ...  # cands/manuscrito como hoje; info[i]["origem"] = origem
                continue
            if tipo is TipoPagina.HIBRIDA_COM_OCR:
                if reocr_hibrido == "sempre":
                    # spec §7: remove a camada e-proc e reOCRiza a página
                    _remover_camada_texto(pdf, page)
                    tarefas.append({"idx": i, "modo": "pagina", ...})
                else:   # auto + deficiente: ADITIVO — OCR da região do scan,
                        # sem tocar na camada/moldura existente
                    tarefas.append({"idx": i, "modo": "regioes",
                                    "escala": _escala_render(page),
                                    "mediabox": mediabox,
                                    "cands": [bbox_scan]})
                info[i] = {"blocos": [], "manuscrito": manuscritos[i],
                           "origem": "camada e-proc incompleta — revisar"}
                continue
            # TEXTO_CORROMPIDO / IMAGEM_SEM_OCR: caminho atual intocado
            info.setdefault(i, {...})["origem"] = "OCR do LIMPAPDF"
```

  Notas de implementação obrigatórias:
  - No `montar()` do modo "regioes" de página híbrida-deficiente, **não**
    registrar os blocos em `info[i]["blocos"]` (o texto invisível já fica no
    PDF e sai no corpo do `.md` — sem blockquote gigante); manter o dedup
    `_texto_contido` contra `existentes[i]`.
  - `origem` para TODAS as páginas (mesmo as sem OCR) — `info[i]` passa a
    existir para toda página quando OCR está ligado.
  - O CTM residual já é neutralizado por `_ocr_camada` — nada a fazer (§7).
- [ ] **Step 3: rodar os testes** (`pytest tests/test_classificador.py -v`).
- [ ] **Step 4: regressão de decisões** — atualizar `decisoes_ocr.py` para
  usar `classificar_pagina` + política (espelha a nova pré-passagem), rodar:
  SIG deve dar **zero** mudança; `ex1` mostra `[mudanca esperada]
  pular -> regioes:1` nas 29+2 páginas deficientes. Regravar baseline
  (`--baseline`) DEPOIS de confirmado.
- [ ] **Step 5: commit** (`feat: embutir_ocr usa classificar_pagina; --reocr-hibrido auto/nunca/sempre`).

---

### Task 4: Origem por página no `.md`

**Files:**
- Modify: `limpa_pdf_mpsc.py:1495-1563` (`exportar_md`)

**Interfaces:**
- Consumes: `info_ocr[i]["origem"]` (Task 3).

- [ ] **Step 1:** logo após `sec = [f"## Página {num} de {total}", ""]`:

```python
        origem = info.get("origem")
        if origem:
            sec += [f"_[{origem}]_", ""]
```

- [ ] **Step 2: teste manual dirigido:** rodar o pipeline completo em `ex1.pdf`
  (CLI: `python limpa_pdf_mpsc.py exemplos/ex1.pdf --saida <tmp> --md --ocr
  --sem-cabecalho`) e conferir no `.md`: páginas 2-30 com
  `_[camada e-proc incompleta — revisar]_` E corpo de OCR presente; página 1
  com `_[texto nativo]_`; página 23 com `_[camada e-proc reaproveitada]_`.
- [ ] **Step 3: commit** (`feat: .md marca a origem do texto de cada página`).

---

### Task 5: CLI, `.bat` e changelog

**Files:**
- Modify: `limpa_pdf_mpsc.py:1-160` (docstring/ajuda), `:2526+` (argparse),
  chamada de `embutir_ocr` no `main()` (~linha 2583)
- Modify: `Limpar_PDFs_com_OCR.bat` (comentário sobre o novo flag)

- [ ] **Step 1: argparse:**

```python
    ap.add_argument("--reocr-hibrido", choices=("auto", "nunca", "sempre"),
                    default=REOCR_HIBRIDO_PADRAO,
                    help="Páginas com scan + camada de texto existente: "
                         "'auto' (padrão) reusa a camada quando suficiente e "
                         "roda o OCR próprio só quando ela é deficiente; "
                         "'nunca' sempre reusa; 'sempre' força o OCR próprio "
                         "(mais lento e pode não melhorar).")
```

  Passar `reocr_hibrido=args.reocr_hibrido` na chamada de `embutir_ocr` do
  `main()`. Em `sempre`, imprimir o aviso de lentidão uma vez.
- [ ] **Step 2: docstring v2.10** (changelog no estilo v2.8/v2.9: classificador
  de 4 tipos, detecção de scan em form (e-proc/TJSC), suficiência por
  densidade, flag `--reocr-hibrido`, origem por página no `.md`).
- [ ] **Step 3: `planejar()`** — contar como páginas de OCR também as híbridas
  deficientes (senão a barra de progresso da GUI mente): no varrimento rápido
  (~linha 2451-2467), substituir o teste por `classificar_pagina` quando o
  arquivo tiver Form XObject de scan; medir o custo (o render 72 dpi é
  ms/página; se o `planejar` ficar > 2x mais lento num SIG grande, manter o
  teste antigo para páginas sem forms — decisão registrada em comentário).
- [ ] **Step 4: commit** (`feat: flag --reocr-hibrido na CLI + changelog v2.10`).

---

### Task 6: Portão de qualidade no `ex1.pdf` (obrigatório antes de consolidar)

**Files:**
- Create: `portao_eproc.py` (raiz, ao lado de `auditoria_limpeza.py`)
- Modify: `RELATORIO_EPROC.md` (tabela antes/depois, gerada pelo script)

- [ ] **Step 1: script** que roda o pipeline completo sobre `ex1.pdf` em dois
  modos (`nunca` × `auto`) para a amostra fixa: pág. 2 (deficiente típica),
  pág. 8/9 (muita tinta), pág. 23 (boa/quase em branco — controle), pág. 33
  (foto). Para cada página e modo, medir: chars extraíveis, palavras únicas,
  confiança média do Tesseract (do `image_to_data` da própria execução).
  Critérios de APROVAÇÃO (o `auto` só fica se):
  - chars(auto) >= chars(nunca) em TODAS as páginas da amostra (aditivo →
    estruturalmente garantido; o teste confirma);
  - a moldura ("Evento 1", nº do processo) continua presente em `auto`;
  - conf média do OCR embutido >= 40 (o corte por palavra já garante);
  - pág. 23 (não deficiente) permanece IDÊNTICA nos dois modos.
- [ ] **Step 2:** anexar a tabela ao `RELATORIO_EPROC.md` (seção "## 7.
  Portão de qualidade") e citar os números no commit.
- [ ] **Step 3: commit** (`test: portão de qualidade e-proc aprovado (tabela no relatório)`).

---

### Task 7: Investigar o "apagou demais" nas páginas de separação (1 e 32)

**Files:**
- Create: nota em `RELATORIO_EPROC.md` (seção "## 8. Páginas de separação")

- [ ] **Step 1:** instrumentar `_motivo_remocao` (só em sessão de depuração,
  sem commitar) sobre `ex1.pdf` pág. 1 e registrar QUAL motivo removeu cada
  elemento de texto e POR QUE o rollback (`LIMITE_PERDA_PAGINA`) não
  disparou (hipótese: motivos "calibrados" — boiler/cluster — são isentos da
  contagem de perda).
- [ ] **Step 2:** documentar a causa-raiz no relatório com recomendação. **Não
  alterar o limpador neste plano** — é superfície do SIG; a correção (se
  desejada) vira tarefa própria com regressão, decidida pelo usuário.

---

### Task 8: Regressão final + verificação de ponta a ponta

- [ ] **Step 1:** `python tests/regressao/decisoes_ocr.py` → OK (SIG zero
  mudanças).
- [ ] **Step 2:** `python tests/regressao/verificar_regressao.py` → OK
  (limpeza: moldura continua removida, miolo não piora — inclusive `ex1`).
- [ ] **Step 3:** `pytest tests/ -v` → tudo verde.
- [ ] **Step 4:** pipeline completo em `ex1.pdf` e num SIG grande
  (`exemplo3.pdf`): conferir `.md` (origens, corpo recuperado no e-proc,
  saída do SIG byte a byte igual à do master para o mesmo arquivo — comparar
  os `.md`).
- [ ] **Step 5:** GUI: `python gui.py`, processar `ex1.pdf` com OCR ligado
  (usa o default `auto` sem mudança na GUI) — barra de progresso conta as
  páginas híbridas (Task 5.3).
- [ ] **Step 6:** commit final + apresentar o diff completo ao usuário
  (regra 4 do atl.md). O `.exe` (PyInstaller) será reempacotado só APÓS o
  merge aprovado — validar `freeze_support` (já presente) e o critério de
  aceite "exe continua funcionando" na fase de empacotamento da v2.10.

## Self-review (feito na escrita)

- §4 diagnóstico ✔ (feito antes deste plano); §5 classificador → Task 2;
  §6 suficiência → Task 2/3; §7 flag+padrão → Task 3/5; §8 origem → Task 4;
  §9 portão → Task 6, regressão → Task 1/8; §10 entregáveis → Tasks 1-6;
  §11 aceites → Task 8 (exe: adiado p/ empacotamento, registrado).
- Descoberta fora do escopo original (páginas de separação apagadas) →
  Task 7 (investigação + relatório, sem mexer no limpador).
- Bug latente `"\Image"` → documentado; NÃO corrigido neste plano (superfície
  SIG); candidata a tarefa futura com regressão própria.
