# -*- coding: utf-8 -*-
"""diag_eproc.py — Diagnóstico dos PDFs do e-proc/TJSC (atl.md §4).

Gera RELATORIO_EPROC.md a partir de exemplos/ex1.pdf (original do e-proc,
com camada de OCR do próprio e-proc) e exemplos/ex1 limpo.pdf (saída atual
do Limpa PDF), medindo POR PÁGINA:

  1. Tipo aparente: imagem de página inteira? camada de texto? aproveitável
     pelo critério atual (_texto_e_aproveitavel)?
  2. Métricas da camada: nº de chars, fração alfanumérica, fração de lixo
     (controle/PUA) e DENSIDADE = chars extraídos ÷ área de tinta visível
     (pixels escuros num render rápido em baixa resolução).
  3. Classificação proposta (atl.md §5) e estratégia que o novo código
     adotaria.
  4. Comparação ex1.pdf × ex1 limpo.pdf: o texto final casa com a camada do
     e-proc? Há páginas em que o limpo ficou praticamente sem texto?

Só MEDIÇÃO — nenhuma alteração de código de produção. Reutiliza as funções
vivas de limpa_pdf_mpsc para que o diagnóstico reflita exatamente as
decisões atuais.
"""

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium

from limpa_pdf_mpsc import (
    IMG_PAGINA_FRAC,
    OCR_MIN_CHARS_AVAL,
    _elementos,
    _grupo,
    _qualidade_texto,
    _texto_e_aproveitavel,
    _tiras_corpo,
)

# Render de baixa resolução para medir a "área de tinta" (spec §4.2): 72 dpi
# basta para distinguir página cheia de texto de página quase vazia, e roda
# em ms/página.
DIAG_RENDER_ESCALA = 1.0        # 1.0 = 72 dpi no pypdfium2
# Pixel "de tinta": abaixo deste nível de cinza (0-255). 128 separa texto
# preto/cinza-escuro do fundo branco e do serrilhado claro de scan.
DIAG_LIMIAR_TINTA = 128
# Densidade (chars extraídos por 1000 px de tinta a 72 dpi) abaixo da qual a
# camada de uma página HÍBRIDA é considerada DEFICIENTE. PROVISÓRIO — este
# relatório existe para calibrá-la (medido em ex1.pdf: páginas nativas boas
# ficam em 54,6-65,5; híbridas só-com-moldura, em 1,3-40,6).
DIAG_DENS_MIN_HIBRIDO = 45.0

PASTA = Path(__file__).parent
ORIGINAL = PASTA / "exemplos" / "ex1.pdf"
LIMPO = PASTA / "exemplos" / "ex1 limpo.pdf"
SAIDA = PASTA / "RELATORIO_EPROC.md"


def _fracao_tinta(pg_pdfium):
    """Fração de pixels escuros (tinta) num render rápido em baixa resolução."""
    bmp = pg_pdfium.render(scale=DIAG_RENDER_ESCALA)
    img = bmp.to_pil().convert("L")
    hist = img.histogram()          # 256 posições
    escuros = sum(hist[:DIAG_LIMIAR_TINTA])
    total = img.width * img.height
    return (escuros / total) if total else 0.0, total


# Área mínima (em pixels da imagem embutida) para considerar que um Form
# XObject carrega um SCAN de página (e não um logo/QR). O scan do e-proc tem
# 1656x2339 = 3,9 Mpx; logos/QR ficam ordens de grandeza abaixo.
DIAG_MIN_PX_SCAN = 300_000


def _form_tem_imagem_grande(xo, nivel=0):
    """True se o Form XObject contém (recursivamente) uma imagem 'de scan'
    (>= DIAG_MIN_PX_SCAN pixels)."""
    if nivel > 3:
        return False
    try:
        sub = xo.get("/Resources", None)
        xobjs = dict(sub.get("/XObject", {})) if sub is not None else {}
    except Exception:
        return False
    for _nome, o in xobjs.items():
        st = str(o.get("/Subtype", ""))
        if st == "/Image":
            try:
                if int(o.get("/Width", 0)) * int(o.get("/Height", 0)) \
                        >= DIAG_MIN_PX_SCAN:
                    return True
            except Exception:
                pass
        elif st == "/Form" and _form_tem_imagem_grande(o, nivel + 1):
            return True
    return False


def _mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


def _forms_pagina_inteira(page_pike, W, H):
    """Detecção CONSCIENTE DE FORM (ausente no código vivo): páginas do
    e-proc desenham o scan dentro de um Form XObject (Do de /TPLn), que
    _elementos não enxerga (não desce em forms; e o ramo de imagem via Do
    compara com "\\Image" — bug latente, nunca casa). Aqui rastreamos o CTM
    no stream DE PÁGINA e, para cada Do de Form com imagem grande dentro,
    medimos a área da colocação do BBox do form na página."""
    from pikepdf import parse_content_stream
    try:
        instrs = list(parse_content_stream(page_pike))
    except Exception:
        return False, 0
    res = page_pike.get("/Resources", pikepdf.Dictionary())
    xobjs = res.get("/XObject", None)
    if xobjs is None or not W or not H:
        return False, 0
    xobjs = dict(xobjs)
    ctm = (1, 0, 0, 1, 0, 0)
    pilha = []
    inteira = False
    n_forms_img = 0
    for operands, op in instrs:
        o = str(op)
        if o == "q":
            pilha.append(ctm)
        elif o == "Q":
            ctm = pilha.pop() if pilha else (1, 0, 0, 1, 0, 0)
        elif o == "cm" and len(operands) == 6:
            try:
                ctm = _mul(tuple(float(v) for v in operands), ctm)
            except Exception:
                pass
        elif o == "Do" and operands:
            xo = xobjs.get(operands[0])
            if xo is None or str(xo.get("/Subtype", "")) != "/Form":
                continue
            if not _form_tem_imagem_grande(xo):
                continue
            n_forms_img += 1
            try:
                bb = [float(v) for v in xo.get("/BBox")]
                m = xo.get("/Matrix", None)
                m = tuple(float(v) for v in m) if m is not None \
                    else (1, 0, 0, 1, 0, 0)
            except Exception:
                continue
            mt = _mul(m, ctm)
            cantos = []
            for x, y in ((bb[0], bb[1]), (bb[2], bb[1]),
                         (bb[0], bb[3]), (bb[2], bb[3])):
                cantos.append((mt[0] * x + mt[2] * y + mt[4],
                               mt[1] * x + mt[3] * y + mt[5]))
            xs = [p[0] for p in cantos]
            ys = [p[1] for p in cantos]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if w >= W * IMG_PAGINA_FRAC and h >= H * IMG_PAGINA_FRAC:
                inteira = True
    return inteira, n_forms_img


def _info_imagens(page_pike):
    """Cobertura de imagem da página: (tem_pagina_inteira, maior_fracao, n).

    1º tenta a detecção viva (_elementos: imagem única >= IMG_PAGINA_FRAC ou
    tiras); depois a detecção consciente de form (e-proc)."""
    els = _elementos(page_pike)
    W, H = _grupo(page_pike)
    area_pag = (W * H) if W and H else 0
    maior = 0.0
    inteira = False
    n_imgs = 0
    for kind, _key, bbox, _instrs, rot in (els or []):
        if kind not in ("I", "II") or not bbox or rot:
            continue
        n_imgs += 1
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        maior = max(maior, (w * h) / area_pag if area_pag else 0.0)
        if w >= W * IMG_PAGINA_FRAC and h >= H * IMG_PAGINA_FRAC:
            inteira = True
    if not inteira and els and _tiras_corpo(els, W, H):
        inteira = True
    via_form = False
    if not inteira:
        via_form, n_forms = _forms_pagina_inteira(page_pike, W, H)
        inteira = inteira or via_form
        n_imgs += n_forms
    return inteira, maior, n_imgs, via_form


def _classificar(tem_img_inteira, texto):
    """Classificação proposta (atl.md §5) e estratégia correspondente."""
    aproveitavel = _texto_e_aproveitavel(texto)
    if aproveitavel and not tem_img_inteira:
        return "NATIVA_DIGITAL", "extrai texto, sem OCR"
    if aproveitavel and tem_img_inteira:
        return "HIBRIDA_COM_OCR", "reusa camada existente (padrao)"
    if len(texto.strip()) >= OCR_MIN_CHARS_AVAL:
        return "TEXTO_CORROMPIDO", "remove camada e roda OCR"
    return "IMAGEM_SEM_OCR", "roda OCR proprio"


def _palavras(texto, min_len=4):
    return {p.lower() for p in texto.split() if len(p) >= min_len and p.isalnum()}


def medir(caminho):
    """Métricas por página de um PDF: lista de dicts."""
    doc = pdfium.PdfDocument(str(caminho))
    pdf = pikepdf.open(caminho)
    linhas = []
    try:
        for i, page_pike in enumerate(pdf.pages):
            tp = doc[i].get_textpage()
            texto = (tp.get_text_range() or "").strip()
            tp.close()
            frac_alnum, frac_lixo = _qualidade_texto(texto)
            tinta, total_px = _fracao_tinta(doc[i])
            px_tinta = tinta * total_px
            # densidade: chars por 1000 pixels de tinta (norm. p/ leitura)
            dens = (len(texto) / px_tinta * 1000) if px_tinta else 0.0
            inteira, maior_img, n_imgs, via_form = _info_imagens(page_pike)
            classe, estrategia = _classificar(inteira, texto)
            deficiente = (classe == "HIBRIDA_COM_OCR"
                          and dens < DIAG_DENS_MIN_HIBRIDO)
            linhas.append({
                "pag": i + 1,
                "chars": len(texto),
                "frac_alnum": frac_alnum,
                "frac_lixo": frac_lixo,
                "frac_tinta": tinta,
                "densidade": dens,
                "img_inteira": inteira,
                "via_form": via_form,
                "deficiente": deficiente,
                "maior_img": maior_img,
                "n_imgs": n_imgs,
                "aproveitavel": _texto_e_aproveitavel(texto),
                "classe": classe,
                "estrategia": estrategia,
                "texto": texto,
            })
    finally:
        pdf.close()
        doc.close()
    return linhas


def main():
    for p in (ORIGINAL, LIMPO):
        if not p.exists():
            raise SystemExit(f"ERRO: arquivo de exemplo ausente: {p}")

    orig = medir(ORIGINAL)
    limpo = medir(LIMPO)

    md = []
    md.append("# RELATORIO_EPROC — diagnóstico de `ex1.pdf` (e-proc/TJSC)\n")
    md.append(f"- Original: `{ORIGINAL.name}` — {len(orig)} página(s)")
    md.append(f"- Limpo:    `{LIMPO.name}` — {len(limpo)} página(s)")
    md.append(f"- Critério atual de aproveitável: `_texto_e_aproveitavel` "
              f"(>= {OCR_MIN_CHARS_AVAL} chars, frac_alnum >= 0.45, "
              f"frac_lixo <= 0.20)")
    md.append(f"- Imagem de página inteira: >= {IMG_PAGINA_FRAC:.0%} da "
              f"largura E altura (ou tiras emendadas)\n")

    md.append("## 1. Página a página — `ex1.pdf` (original do e-proc)\n")
    md.append("Img inteira 'via form' = o scan está DENTRO de um Form "
              "XObject (Do de /TPLn), invisível para `_elementos` hoje.\n")
    md.append("| Pág | Chars | Alnum | Lixo | Tinta | Dens (ch/1k px) | "
              "Imgs | Img inteira? | Aproveitável? | Camada deficiente? | "
              "Classe proposta | Estratégia |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|---|---|")
    for r in orig:
        inteira = ("sim (via form)" if r["img_inteira"] and r["via_form"]
                   else ("sim" if r["img_inteira"] else "nao"))
        md.append(
            f"| {r['pag']} | {r['chars']} | {r['frac_alnum']:.2f} | "
            f"{r['frac_lixo']:.2f} | {r['frac_tinta']:.3f} | "
            f"{r['densidade']:.1f} | {r['n_imgs']} | {inteira} | "
            f"{'sim' if r['aproveitavel'] else 'NAO'} | "
            f"{'SIM' if r['deficiente'] else 'nao'} | "
            f"{r['classe']} | {r['estrategia']} |")

    md.append("\n## 2. Página a página — `ex1 limpo.pdf` (saída atual)\n")
    md.append("| Pág | Chars | Alnum | Lixo | Tinta | Img inteira? | "
              "Aproveitável? |")
    md.append("|---:|---:|---:|---:|---:|:--:|:--:|")
    for r in limpo:
        md.append(
            f"| {r['pag']} | {r['chars']} | {r['frac_alnum']:.2f} | "
            f"{r['frac_lixo']:.2f} | {r['frac_tinta']:.3f} | "
            f"{'sim' if r['img_inteira'] else 'nao'} | "
            f"{'sim' if r['aproveitavel'] else 'NAO'} |")

    md.append("\n## 3. Comparação original × limpo (o limpo preservou a "
              "camada do e-proc?)\n")
    md.append("| Pág | Chars orig | Chars limpo | Razão | Palavras da camada "
              "presentes no limpo | Observação |")
    md.append("|---:|---:|---:|---:|---:|---|")
    n = min(len(orig), len(limpo))
    for i in range(n):
        o, l = orig[i], limpo[i]
        razao = (l["chars"] / o["chars"]) if o["chars"] else float("nan")
        po, pl = _palavras(o["texto"]), _palavras(l["texto"])
        cobertura = (len(po & pl) / len(po)) if po else float("nan")
        obs = []
        if o["chars"] >= OCR_MIN_CHARS_AVAL and l["chars"] < OCR_MIN_CHARS_AVAL:
            obs.append("LIMPO PRATICAMENTE SEM TEXTO")
        elif razao == razao and razao < 0.5:
            obs.append("limpo perdeu >50% dos chars")
        if cobertura == cobertura and cobertura >= 0.8:
            obs.append("camada e-proc preservada")
        md.append(
            f"| {i + 1} | {o['chars']} | {l['chars']} | "
            f"{razao:.2f} | {cobertura:.2f} | {'; '.join(obs) or '-'} |")
    if len(orig) != len(limpo):
        md.append(f"\n**ATENÇÃO:** nº de páginas difere "
                  f"({len(orig)} × {len(limpo)}).")

    md.append("\n## 4. Resumo por classe proposta\n")
    classes = {}
    for r in orig:
        classes.setdefault(r["classe"], []).append(r["pag"])
    for classe, pags in sorted(classes.items()):
        md.append(f"- **{classe}**: {len(pags)} página(s) — "
                  f"{', '.join(map(str, pags[:30]))}"
                  f"{'...' if len(pags) > 30 else ''}")

    md.append("\n## 5. Candidatas a camada DEFICIENTE (calibragem de "
              "`FRAC_TEXTO_MIN_HIBRIDO`)\n")
    md.append("Páginas híbridas ordenadas por densidade (chars por 1000 px "
              "de tinta) — as de densidade mais baixa têm muita tinta e "
              "pouco texto reconhecido:\n")
    hibridas = sorted((r for r in orig if r["classe"] == "HIBRIDA_COM_OCR"),
                      key=lambda r: r["densidade"])
    if hibridas:
        md.append("| Pág | Chars | Tinta | Dens (ch/1k px) |")
        md.append("|---:|---:|---:|---:|")
        for r in hibridas:
            md.append(f"| {r['pag']} | {r['chars']} | {r['frac_tinta']:.3f} "
                      f"| {r['densidade']:.1f} |")
    else:
        md.append("*Nenhuma página híbrida encontrada.*")

    md.append("\n## 6. Conclusões do diagnóstico (estrutura confirmada por "
              "inspeção)\n")
    md.append("""\
1. **`ex1.pdf` NÃO tem camada de OCR do corpo.** A hipótese do prompt
   ("camada de OCR prévia gerada pelo e-proc") **não se confirma** neste
   arquivo: o texto extraível de cada página escaneada (~264 chars,
   constante) é só a **moldura** — o rodapé do e-proc ("Processo ...,
   Evento 1, ..., Página N") e o carimbo do SGP-e ("Pág. X de Y - Documento
   assinado digitalmente..."). Dentro dos Form XObjects `/TPLn` há
   exatamente 1 `Tj` (o carimbo lateral) e a imagem do scan — nenhum texto
   de corpo. A camada do e-proc aqui é o caso-limite da "camada deficiente"
   (§6 do prompt): existe, é limpa (0% lixo), mas não diz nada do corpo.
2. **O scan fica DENTRO de um Form XObject** (`Do` de `/TPLn`, imagem
   1656x2339 DCT/CCITT ocupando a página inteira). `_elementos` não desce
   em forms, e o ramo de imagem via `Do` compara Subtype com `"\\Image"`
   (barra invertida — nunca casa com `"/Image"`; latente desde o commit
   inicial). Resultado: **nenhuma** imagem é vista nas páginas do e-proc —
   a detecção de "imagem de página inteira" precisa tornar-se consciente
   de form para o classificador (sem alterar as decisões do SIG).
3. **O comportamento atual reproduz o defeito relatado pelo usuário:** as
   31 páginas escaneadas passam em `_texto_e_aproveitavel` (264 chars bons
   da moldura) → `embutir_ocr` pula o OCR → o corpo inteiro do TC se perde.
   No `ex1 limpo.pdf`, as páginas 2-30 têm só os ~212 chars da moldura.
4. **"Apagou demais" nas páginas NATIVAS do e-proc:** as páginas de
   separação (1 e 32) saem do limpador com 16-17 chars e tinta 0.000
   (visualmente em branco — perdem "AUTO DE PRISÃO EM FLAGRANTE",
   nº do processo etc.), e o rollback da v2.9 não disparou. Investigar na
   implementação (motivos exentos de LIMITE_PERDA_PAGINA?).
5. **A densidade separa bem os casos** (chars por 1000 px de tinta a 72
   dpi): páginas nativas boas medem **54,6-65,5**; híbridas só-moldura,
   **1,3-40,6**. Proposta: `FRAC_TEXTO_MIN_HIBRIDO = 45` (meio do vão).
   Exceção correta: pág. 23 (scan quase em branco, tinta 0.008) fica com
   densidade 63,8 → reusa a camada; não há quase nada a recuperar.
6. **Regressão do SIG:** os PDFs originais do SIG não estão mais em
   `exemplos/` (pasta git-ignored); estão em
   `C:\\Users\\User\\Desktop\\PDFs para Teste\\exemplos\\`. Para rodar a
   bateria de `tests/regressao/verificar_regressao.py` é preciso
   recolocá-los em `exemplos/`.
""")
    SAIDA.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Relatorio gravado em {SAIDA}")
    print(f"Paginas: {len(orig)} orig / {len(limpo)} limpo; "
          f"classes: { {k: len(v) for k, v in classes.items()} }")


if __name__ == "__main__":
    main()
