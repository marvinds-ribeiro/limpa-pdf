# Limpa PDF v2.8 Implementation Plan — .md estruturado, OCR de imagens embutidas, divisão por MB

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A saída de extração passa a ser sempre um `.md` estruturado (peças, páginas, tabelas reais), o OCR passa a ler também imagens embutidas no meio de páginas com texto (prints de WhatsApp = prova), os avisos de tabela/imagem somem, o OCR vem ligado por padrão na GUI e a divisão passa a ser por tamanho real em MB (crescer-gravar-medir).

**Architecture:** Toda a lógica vive em `limpa_pdf_mpsc.py` (base única, v2.7 → v2.8). `exportar_txt` é substituída por `exportar_md`; `embutir_ocr` ganha um passo de OCR por região e passa a retornar `(n_ocr, info_ocr)`; `dividir_pdf` muda de `max_pag` para `max_mb`. A GUI (`gui.py`) só re-liga as funções (não reimplementa lógica). Pipeline preservado: limpa → OCR → numerar → dividir → exportar.

**Tech Stack:** pikepdf, pdfplumber, pypdfium2, pytesseract, Pillow, opencv-headless, PySide6, pytest.

## Global Constraints

- Preservação conservadora: na dúvida, NÃO remover; nunca perder página nem dado (CLAUDE.md §5).
- 100% local/offline em tempo de uso.
- Toda grandeza ajustável vira constante nomeada no topo do módulo, com comentário do efeito.
- Comentários e strings de UI em português.
- Constantes novas (valores exatos do spec): `IMG_OCR_FRAC_MIN = 0.02`, `MANUSCRITO_MAX_TEXTO = 40`, `MANUSCRITO_FRAC_MIN = 0.25`, `TAB_MIN_LINHAS = 2`, `TAB_MIN_COLUNAS = 2`, `MAX_MB_PARTE = 100`, `DIV_MARGEM_SEGURANCA = 0.90`. Reusa `IMG_PAGINA_FRAC = 0.80` e corte de confiança `conf >= 40` no PDF.
- Ordem de implementação do spec: Tarefa 1 → 2 → 3 → 4 → 5 (aqui expandida em 8 tasks, na mesma ordem).
- Baseline: 25 testes passam (`python -m pytest tests -q`). Nenhuma task pode regredir isso.
- PDFs de validação: `exemplo 1.pdf` (espaço no nome!), `exemplo2.pdf`, `exemplo3.pdf`, `exemplo9.pdf` na raiz; `exemplos/exemplo4..8.pdf`.
- `LEIA-ME.txt` e `Proposta_Limpa_PDF_SIG_v2.docx` NÃO existem mais no repositório (só os PDFs `Limpa_PDF_Manual_do_Usuario.pdf` / `Apresenta LimpaPDF.pdf`, não editáveis). A task de docs atualiza CLAUDE.md + docstring + .bat e REPORTA essa ausência ao usuário em vez de inventar arquivos.

**Decisão técnica registrada (duplicação camada↔md):** a camada invisível de OCR de região é anexada ao FIM do content stream, então a extração de texto da página devolve esse texto no FIM do corpo. Para o `.md` não duplicar, `exportar_md` remove esse sufixo do corpo (comparação tolerante a espaços) e apresenta o texto no bloco marcado `> **[Texto extraído de imagem na página N]**`. Se a remoção falhar (extrator reordenou), o bloco é emitido assim mesmo — duplicar é aceitável, perder não. A deduplicação semântica (imagem cujo texto já está no corpo ORIGINAL) acontece dentro de `embutir_ocr`, ANTES de embutir, comparando com o texto pré-embed.

**Decisão técnica registrada (tabelas):** o texto das células também aparece no corpo extraído; a tabela Markdown é emitida DEPOIS do corpo, sem tentar removê-lo do corpo (cirurgia frágil). Redundância marcada > risco de perda.

---

### Task 1: `exportar_md` + detecção de peças + tabelas Markdown (núcleo)

**Files:**
- Modify: `limpa_pdf_mpsc.py` (substitui `exportar_txt` por `exportar_md` + helpers + constantes)
- Test: `tests/test_exportar_md.py` (novo)

**Interfaces:**
- Produces: `exportar_md(pdf_path: Path, md_path: Path, offset: int = 1, total: int = 0, info_ocr: dict | None = None)`; helpers puros `_detectar_peca(linha) -> str|None`, `_marcar_pecas(texto) -> str`, `_tabela_para_md(linhas) -> str|None`, `_tabelas_md(pdf_path) -> dict[int, list[str]]`, `_remover_sufixo_tolerante(corpo, sufixo) -> str|None`, `_extrair_paginas(pdf_path) -> list[str]|None`, `_cabecalho_md(pdf_path, paginas, total) -> str`.
- Consumes: `_texto_e_aproveitavel` (existente, não muda).
- `info_ocr` (preenchido na Task 4): `{pagina_global_0based: {"blocos": [(texto: str, conf_media: float)], "manuscrito": bool}}`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_exportar_md.py`:

```python
import pikepdf
import pytest
from pathlib import Path

import limpa_pdf_mpsc as core


def _pdf_texto(path: Path, paginas_texto: list[str]):
    """PDF sintético com texto Helvetica extraível (uma string por página)."""
    pdf = pikepdf.new()
    for txt in paginas_texto:
        page = pdf.add_blank_page(page_size=(612, 792))
        fonte = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
            Encoding=pikepdf.Name.WinAnsiEncoding))
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=fonte))
        ops = [b"BT /F1 12 Tf 72 720 Td 14 TL"]
        for lin in txt.splitlines():
            s = (lin.encode("cp1252", "replace")
                 .replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)"))
            ops.append(b"(" + s + b") Tj T*")
        ops.append(b"ET")
        page.Contents = pdf.make_stream(b"\n".join(ops))
    pdf.save(path)


def test_detectar_peca_conservador():
    assert core._detectar_peca("DESPACHO") == "DESPACHO"
    assert core._detectar_peca("  TERMO DE DECLARACOES  ") == "TERMO DE DECLARACOES"
    assert core._detectar_peca("OFÍCIO Nº 123/2026") == "OFÍCIO Nº 123/2026"
    # prosa nunca vira heading
    assert core._detectar_peca("o despacho foi proferido ontem") is None
    assert core._detectar_peca("Despacho") is None            # não é MAIÚSCULA
    assert core._detectar_peca("DESPACHOU O JUIZ QUE") is None # rótulo colado a letra
    assert core._detectar_peca("A" * 80) is None               # linha longa demais
    assert core._detectar_peca("") is None


def test_tabela_para_md_filtro_2x2():
    assert core._tabela_para_md([["a"], ["b"]]) is None          # 1 coluna
    assert core._tabela_para_md([["a", "b"]]) is None            # 1 linha
    md = core._tabela_para_md([["Nome", "Valor"], ["x", "1|2"]])
    assert md.splitlines()[0] == "| Nome | Valor |"
    assert "---" in md.splitlines()[1]
    assert "\\|" in md                                           # pipe escapado


def test_remover_sufixo_tolerante():
    assert core._remover_sufixo_tolerante("corpo aqui\nfim ocr", "fim  ocr") == "corpo aqui"
    assert core._remover_sufixo_tolerante("corpo aqui", "outro texto") is None


def test_exportar_md_estrutura(tmp_path):
    pdf = tmp_path / "doc.pdf"
    _pdf_texto(pdf, ["PORTARIA\ntexto da portaria", "pagina dois de texto corrido"])
    md = tmp_path / "doc.md"
    core.exportar_md(pdf, md, offset=1, total=2)
    t = md.read_text(encoding="utf-8")
    assert t.startswith("# doc")
    assert "**Total de páginas:** 2" in t
    assert "## Página 1 de 2" in t and "## Página 2 de 2" in t
    assert "### PORTARIA" in t
    assert "\n---\n" in t
    assert ">> AVISO" not in t and "REDE DE SEGURANCA" not in t
    assert "|" not in t.replace("\\|", "")   # sem pipes: nenhuma tabela válida


def test_exportar_md_pagina_sem_texto(tmp_path):
    pdf = tmp_path / "vazio.pdf"
    _pdf_texto(pdf, [""])
    md = tmp_path / "vazio.md"
    core.exportar_md(pdf, md)
    t = md.read_text(encoding="utf-8")
    assert "sem texto aproveitável" in t


def test_exportar_md_blocos_info_ocr(tmp_path):
    pdf = tmp_path / "img.pdf"
    _pdf_texto(pdf, ["texto de corpo da pagina"])
    md = tmp_path / "img.md"
    info = {0: {"blocos": [("conversa do whatsapp extraida", 85.0),
                           ("trecho ruim", 30.0)],
                "manuscrito": False}}
    core.exportar_md(pdf, md, offset=1, total=1, info_ocr=info)
    t = md.read_text(encoding="utf-8")
    assert "> **[Texto extraído de imagem na página 1]**" in t
    assert "> conversa do whatsapp extraida" in t
    assert t.count("baixa confiança de OCR") == 1   # só no bloco de conf 30


def test_exportar_md_manuscrito(tmp_path):
    pdf = tmp_path / "manu.pdf"
    _pdf_texto(pdf, ["texto ocr de manuscrito ruidoso aqui presente"])
    md = tmp_path / "manu.md"
    info = {0: {"blocos": [], "manuscrito": True}}
    core.exportar_md(pdf, md, info_ocr=info)
    t = md.read_text(encoding="utf-8")
    assert "Documento manuscrito — OCR de baixa confiança" in t


def test_exportar_md_offset_continuo(tmp_path):
    pdf = tmp_path / "parte.pdf"
    _pdf_texto(pdf, ["a", "b"])
    md = tmp_path / "parte.md"
    core.exportar_md(pdf, md, offset=151, total=300)
    t = md.read_text(encoding="utf-8")
    assert "## Página 151 de 300" in t and "## Página 152 de 300" in t
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_exportar_md.py -q`
Expected: FAIL/ERROR com `AttributeError: ... '_detectar_peca'` etc.

- [ ] **Step 3: Implementar no `limpa_pdf_mpsc.py`**

Constantes novas (junto de `IMG_EMBUTIDA_FRAC`/`IMG_PAGINA_FRAC`):

```python
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
```

Funções (substituem `exportar_txt`; `_texto_aviso`/avisos ficam para a Task 5 remover):

```python
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
    no filtro mínimo TAB_MIN_LINHAS x TAB_MIN_COLUNAS (falso positivo)."""
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


def _tabelas_md(pdf_path: Path) -> dict:
    """Tabelas REAIS por página (0-based nesta parte), já em Markdown.
    Nunca quebra: sem pdfplumber (ou erro), devolve {} silenciosamente."""
    try:
        import pdfplumber
    except Exception:
        return {}
    out = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, p in enumerate(pdf.pages):
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
    imagem, que a extração devolve no fim do corpo da página."""
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
                total: int = 0, info_ocr: dict | None = None):
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
        num = offset + i
        info = info_ocr.get(offset - 1 + i, {})
        blocos = info.get("blocos", [])
        corpo = texto.strip()
        # A camada invisível do OCR de imagem foi anexada ao FIM do content
        # stream, então a extração devolve esse texto no fim do corpo; tira-se
        # o sufixo para o bloco marcado abaixo não duplicar. Se não casar
        # (extrator reordenou), mantém — duplicar é aceitável, perder não.
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
```

E a constante de confiança (perto dos parâmetros de OCR):

```python
# Confiança média (0-100) abaixo da qual um bloco de OCR de imagem embutida é
# marcado no .md como "baixa confiança — conferir no original".
IMG_OCR_CONF_BAIXA = 60
```

Nota: `exportar_txt` ainda NÃO é apagada nesta task (main/GUI ainda a chamam); a Task 2 troca os chamadores e apaga.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_exportar_md.py tests -q`
Expected: novos testes PASS; os 25 antigos continuam passando.

- [ ] **Step 5: Commit**

```bash
git add limpa_pdf_mpsc.py tests/test_exportar_md.py
git commit -m "feat: v2.8 — exportar_md com peças, metadados e tabelas Markdown"
```

---

### Task 2: ligar o .md no CLI, GUI e .bat (a flag --txt vira --md)

**Files:**
- Modify: `limpa_pdf_mpsc.py` (`main()`: flag `--md` com alias `--txt`, chama `exportar_md`, apaga `exportar_txt`)
- Modify: `gui.py` (Worker: `op["md"]`, `parte.with_suffix(".md")`, `exportar_md`; janela: chave `md`)
- Modify: `Limpar_PDFs_com_OCR.bat` (`--txt` → `--md`, textos)
- Modify: `tests/test_worker.py` (chaves `txt` → `md`)

**Interfaces:**
- Consumes: `exportar_md(parte, md, offset=offset, total=total_pag, info_ocr=None)` (Task 1). `info_ocr=None` até a Task 4.
- Produces: opções da GUI com chave `"md"`; CLI `--md` (e `--txt` como alias oculto de compatibilidade).

- [ ] **Step 1: Atualizar `tests/test_worker.py` (chave `"txt"` → `"md"`) e ver falhar**

Nos três dicionários `opcoes`, trocar `"txt": False` por `"md": False`.
Run: `python -m pytest tests/test_worker.py -q` — Expected: FAIL (`KeyError: 'md'` no Worker atual… na verdade o Worker lê `op["txt"]`, então KeyError: 'txt').

- [ ] **Step 2: `main()` — trocar exportação**

Em `argparse`:

```python
    ap.add_argument("--md", "--txt", dest="md", action="store_true",
                    help="Exporta o conteúdo em Markdown (.md) estruturado"
                         " para colar na IA (--txt é alias antigo)")
```

(Remover o antigo `ap.add_argument("--txt", ...)`.)

No laço final de `main()`, o total de páginas passa a ser calculado SEMPRE (o `exportar_md` precisa dele mesmo sem paginação): mover o `with pikepdf.open(destino)... total_pag = len(_p.pages)` para antes do bloco `if not args.sem_numero:` e reusar. Trocar o bloco do `.txt` por:

```python
        for parte, offset in partes:
            nomes.append(parte.name)
            if args.md:
                md = parte.with_suffix(".md")
                try:
                    exportar_md(parte, md, offset=offset, total=total_pag)
                    if md.is_file():
                        nomes.append(md.name)
                except Exception as e:
                    print(f"   [aviso] falha ao gerar {md.name}: {e}")
```

Apagar a função `exportar_txt` (a chamada some do main e da GUI nesta task).

- [ ] **Step 3: `gui.py` — Worker e opções**

No `Worker._executar`, trocar o bloco final por:

```python
            for parte, offset in partes:
                gerados.append(parte.name)
                if op["md"]:
                    md = parte.with_suffix(".md")
                    try:
                        core.exportar_md(parte, md, offset=offset,
                                         total=total_pag)
                        if md.is_file():
                            gerados.append(md.name)
                    except Exception as e:
                        self.log.emit(f"[AVISO] .md falhou: {e}")
```

com `total_pag` calculado antes da numeração (sempre, não só com `op["paginar"]`):

```python
            total_pag = 0
            try:
                import pikepdf
                with pikepdf.open(destino) as _p:
                    total_pag = len(_p.pages)
            except Exception:
                pass

            if op["paginar"] and total_pag:
                self.log.emit(f"[{k+1}/{total}] Numerando páginas de {arq.name}...")
                try:
                    core.numerar_paginas(destino, total_pag, inicio=1)
                except Exception as e:
                    self.log.emit(f"[AVISO] Numeração falhou: {e}")
```

Em `_iniciar()`, trocar `"txt": self.chk_txt.isChecked(),` por `"md": self.chk_md.isChecked(),` e renomear o widget `self.chk_txt` → `self.chk_md` (o rótulo muda na Task 6). Atualizar o docstring do topo do gui.py (pipeline: `exportar_md`).

- [ ] **Step 4: `.bat`**

Em `Limpar_PDFs_com_OCR.bat`: trocar `--txt` por `--md` na linha do python e o texto final `*_limpo.txt` por `*_limpo.md`.

- [ ] **Step 5: Rodar tudo + fumaça de CLI**

Run: `python -m pytest tests -q` — Expected: PASS.
Run: `python limpa_pdf_mpsc.py "exemplo2.pdf" --sem-cabecalho --md --saida "%TEMP%\lp_t2"` — Expected: gera `exemplo2.pdf` limpo + `exemplo2.md` com `# exemplo2` e `## Página 1 de 1`; sem avisos de tabela/imagem no .md.

- [ ] **Step 6: Commit**

```bash
git add limpa_pdf_mpsc.py gui.py Limpar_PDFs_com_OCR.bat tests/test_worker.py
git commit -m "feat: v2.8 — saída sempre em .md no CLI, GUI e .bat (--txt vira --md)"
```

---

### Task 3: helpers puros do OCR por região (filtro, dedup, refactor da camada)

**Files:**
- Modify: `limpa_pdf_mpsc.py`
- Test: `tests/test_ocr_regioes.py` (novo)

**Interfaces:**
- Produces: `_imagem_candidata_ocr(bbox, W, H) -> bool`; `_texto_contido(menor, maior) -> bool`; `_linhas_texto_ocr(dados, x0, y0, H, sx, sy, dx_px=0.0, dy_px=0.0) -> (list[bytes], list[str], list[int])`; `_escala_render(page) -> float`; `_garantir_fonte(pdf, page, nome)`; constantes `IMG_OCR_FRAC_MIN=0.02`, `IMG_OCR_ZONA_CABECALHO=0.15`, `OCR_DEDUP_FRAC=0.80`, `MANUSCRITO_MAX_TEXTO=40`, `MANUSCRITO_FRAC_MIN=0.25`.
- Consumes: `_normalizar_ocr`, `_larg_helvetica`, `_escapa_pdf` (existentes). `embutir_ocr` e `numerar_paginas` passam a usar `_garantir_fonte`/`_linhas_texto_ocr`/`_escala_render` sem mudar comportamento.

- [ ] **Step 1: Testes que falham**

Criar `tests/test_ocr_regioes.py`:

```python
import limpa_pdf_mpsc as core

W, H = 612.0, 792.0


def _bbox_frac(frac, y0=200.0):
    """bbox com fração de área 'frac', fora da zona de cabeçalho."""
    w = W * 0.6
    h = frac * W * H / w
    return (50.0, y0, 50.0 + w, y0 + h)


def test_filtro_exclui_logo_e_pagina_inteira():
    # logo do MPSC medido: ~0.014 -> fora por fração mínima
    assert not core._imagem_candidata_ocr(_bbox_frac(0.014), W, H)
    # print de WhatsApp medido: 0.024-0.063 -> entra
    assert core._imagem_candidata_ocr(_bbox_frac(0.024), W, H)
    assert core._imagem_candidata_ocr(_bbox_frac(0.063), W, H)
    # página escaneada inteira (>= 0.80): já coberta pelo fluxo existente
    assert not core._imagem_candidata_ocr((0, 0, W, H * 0.9), W, H)


def test_filtro_exclui_zona_cabecalho():
    # imagem grande o bastante, mas colada no topo (15% superior)
    topo = H * (1 - core.IMG_OCR_ZONA_CABECALHO) + 1
    assert not core._imagem_candidata_ocr((50, topo, 350, topo + 100), W, H)


def test_texto_contido_tolerante():
    corpo = "Cuida-se de relatório sobre conversa mantida entre investigados"
    assert core._texto_contido("relatório sobre conversa investigados", corpo)
    assert not core._texto_contido("mensagem inédita sobre transferência bancária", corpo)
    assert not core._texto_contido("", corpo)


def test_linhas_texto_ocr_com_deslocamento():
    dados = {"text": ["Oi"], "conf": ["90"], "left": [10], "top": [20],
             "width": [40], "height": [12]}
    # página inteira (sem deslocamento)
    l0, p0, c0 = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18)
    # mesmo dado vindo de um recorte deslocado 100px/50px
    l1, p1, c1 = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18,
                                        dx_px=100, dy_px=50)
    assert p0 == p1 == ["Oi"] and c0 == c1 == [90]
    assert l0 != l1                      # coordenadas mudaram
    assert b"(Oi) Tj" in l1[0]
    # conf < 40 é descartada (mesmo corte do PDF)
    dados["conf"] = ["30"]
    l2, p2, _ = core._linhas_texto_ocr(dados, 0, 0, 792.0, 0.18, 0.18)
    assert not l2 and not p2
```

Run: `python -m pytest tests/test_ocr_regioes.py -q` — Expected: FAIL (atributos inexistentes).

- [ ] **Step 2: Implementar constantes + helpers**

Junto dos parâmetros de OCR:

```python
# --- OCR por REGIÃO de imagem embutida (v2.8) --------------------------------
# Páginas com texto de corpo podem trazer PRINTS/documentos como imagens
# embutidas (prova!) que o fluxo de página inteira nunca lia. Filtro de
# candidatas (medido nos exemplos reais): logo do MPSC ~0.014 da página;
# prints 0.024-0.063. O corte em 0.02 exclui o logo e mantém os prints.
IMG_OCR_FRAC_MIN = 0.02      # fração mínima da página p/ OCR de região
IMG_OCR_ZONA_CABECALHO = 0.15  # topo da página onde imagem = logo/timbre
# Deduplicação tolerante: fração mínima de palavras (>=4 letras) do texto da
# imagem presentes no corpo para considerá-lo repetido (e não duplicar).
OCR_DEDUP_FRAC = 0.80
# Página MANUSCRITA (best-effort honesto): quase sem texto de corpo e com
# imagem grande. O Tesseract NÃO lê cursiva com fidelidade — o .md marca.
# Medido no exemplo real: 18 chars/página + imagens de fração 0.33.
MANUSCRITO_MAX_TEXTO = 40    # corpo com menos chars que isso = "sem texto"
MANUSCRITO_FRAC_MIN = 0.25   # imagem com fração >= isso = possível manuscrito
```

Helpers (código completo):

```python
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
        x = x0 + left * sx
        base_bbox = y0 + H - (top + hpx) * sy
        larg_pt = max(wpx * sx, 1.0)
        alt_pt = max(hpx * sy, 4.0)
        fs = max(alt_pt / 0.72, 4.0)
        y = base_bbox + alt_pt * 0.18
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
```

Refatorar SEM mudar comportamento: em `embutir_ocr`, substituir o cálculo de escala inline por `_escala_render(page)`, o laço de palavras pelo `_linhas_texto_ocr(dados, x0, y0, H, sx, sy)` e o bloco de fonte por `_garantir_fonte(pdf, page, "/FOCR")`; em `numerar_paginas`, usar `_garantir_fonte(pdf, page, "/FNUM")`.

- [ ] **Step 3: Rodar e ver passar**

Run: `python -m pytest tests -q` — Expected: PASS (novos + antigos).

- [ ] **Step 4: Validar que o refactor não mudou o OCR de página inteira**

Run: `python limpa_pdf_mpsc.py "exemplos\exemplo4.pdf" --sem-cabecalho --md --ocr --saida "%TEMP%\lp_t3"` (exemplo4 é do lote de scans) e conferir que o `.md` traz texto real das páginas escaneadas (sem lixo, sem "sem texto aproveitável" nas páginas com conteúdo).

- [ ] **Step 5: Commit**

```bash
git add limpa_pdf_mpsc.py tests/test_ocr_regioes.py
git commit -m "feat: v2.8 — helpers de OCR por região (filtro, dedup, camada reutilizável)"
```

---

### Task 4: `embutir_ocr` com OCR de imagens embutidas + manuscrito + `info_ocr`

**Files:**
- Modify: `limpa_pdf_mpsc.py` (`embutir_ocr` retorna `(int, dict)`; novas `_ocr_imagens_embutidas`, `_pagina_manuscrita`)
- Modify: `gui.py` e `main()` (recebem o dict e o repassam a `exportar_md`)
- Test: `tests/test_ocr_regioes.py` (integração, com skip se Tesseract ausente)

**Interfaces:**
- Produces: `embutir_ocr(pdf_path, lang, cfg) -> tuple[int, dict]` — dict `{pag_global_0based: {"blocos": [(texto, conf_media)], "manuscrito": bool}}` (só páginas com algo a registrar).
- Consumes: helpers da Task 3; `exportar_md(..., info_ocr=...)` da Task 1; `_elementos`, `_grupo`, `_ctm_residual`, `_inverter_matriz`, `_preparar_imagem_ocr` existentes.

- [ ] **Step 1: Teste de integração que falha**

Acrescentar em `tests/test_ocr_regioes.py`:

```python
import shutil
from pathlib import Path
import pytest

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO1 = RAIZ / "exemplo 1.pdf"


def _tem_tesseract():
    lang, _ = core._preparar_ocr()
    return bool(lang)


@pytest.mark.skipif(not EXEMPLO1.is_file(), reason="exemplo 1.pdf ausente")
def test_ocr_regiao_exemplo1(tmp_path):
    if not _tem_tesseract():
        pytest.skip("Tesseract indisponível")
    alvo = tmp_path / "ex1.pdf"
    shutil.copy(EXEMPLO1, alvo)
    lang, cfg = core._preparar_ocr()
    n_ocr, info = core.embutir_ocr(alvo, lang, cfg)
    # a página tem 1607 chars de corpo + 6 imagens (prints): antes passava
    # batido; agora deve produzir blocos de OCR de imagem
    assert isinstance(info, dict)
    assert any(v["blocos"] for v in info.values()), \
        "nenhum texto extraído dos prints do exemplo 1"
    # e o texto embutido fica extraível no PDF (seleção)
    paginas = core._extrair_paginas(alvo)
    bloco0 = info[0]["blocos"][0][0]
    assert core._texto_contido(bloco0, paginas[0])
```

Run: `python -m pytest tests/test_ocr_regioes.py -q` — Expected: FAIL (`embutir_ocr` retorna int; sem blocos).

- [ ] **Step 2: Implementar**

Novas funções:

```python
def _pagina_manuscrita(page, existente: str) -> bool:
    """Página majoritariamente MANUSCRITA (best-effort honesto): quase sem
    texto de corpo (< MANUSCRITO_MAX_TEXTO chars) e com imagem(ns) de fração
    >= MANUSCRITO_FRAC_MIN. O OCR roda assim mesmo, mas o Tesseract não lê
    cursiva com fidelidade — o .md marca o bloco como baixa confiança."""
    if len((existente or "").strip()) >= MANUSCRITO_MAX_TEXTO:
        return False
    els = _elementos(page)
    if els is None:
        return False
    W, H = _grupo(page)
    area = (W * H) or 1
    return any(
        kind in ("I", "II") and bbox and not rot
        and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / area >= MANUSCRITO_FRAC_MIN
        for kind, _k, bbox, _i, rot in els)


def _ocr_imagens_embutidas(pdf, page, pag_pdfium, lang, cfg_ocr, existente):
    """OCR por REGIÃO das imagens embutidas de uma página que JÁ tem texto de
    corpo (prints de WhatsApp, documentos anexados — possível prova que o
    fluxo de página inteira nunca lia). Para cada imagem candidata (vide
    _imagem_candidata_ocr): recorta SÓ a região da página renderizada,
    pré-processa (_preparar_imagem_ocr) e reconhece; o texto vira camada
    invisível alinhada (mesma matemática da página inteira, deslocada pelo
    recorte) e um bloco para o .md. Texto já contido no corpo é descartado
    (_texto_contido) — não duplica nem embute. Nunca quebra: erro em uma
    região só pula aquela região. Retorna [(texto, conf_media)]."""
    import pytesseract
    els = _elementos(page)
    if els is None:
        return []
    W, H = _grupo(page)
    cands = [bbox for kind, _k, bbox, _ins, rot in els
             if kind in ("I", "II") and bbox and not rot
             and _imagem_candidata_ocr(bbox, W, H)]
    if not cands:
        return []
    escala = _escala_render(page)
    img = pag_pdfium.render(scale=escala).to_pil()
    box = page.mediabox
    mx0, my0 = float(box[0]), float(box[1])
    Wm, Hm = float(box[2]) - mx0, float(box[3]) - my0
    sx, sy = Wm / img.width, Hm / img.height
    linhas_pag, blocos = [], []
    for bbox in cands:
        # bbox em pontos (origem inferior-esquerda) -> recorte px (origem sup.)
        cx0 = max(0, int((bbox[0] - mx0) / sx))
        cx1 = min(img.width, int(math.ceil((bbox[2] - mx0) / sx)))
        cy0 = max(0, int((Hm - (bbox[3] - my0)) / sy))
        cy1 = min(img.height, int(math.ceil((Hm - (bbox[1] - my0)) / sy)))
        if cx1 - cx0 < 8 or cy1 - cy0 < 8:
            continue
        rec = _preparar_imagem_ocr(img.crop((cx0, cy0, cx1, cy1)))
        try:
            dados = pytesseract.image_to_data(
                rec, lang=lang, config=cfg_ocr,
                output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        linhas, palavras, confs = _linhas_texto_ocr(
            dados, mx0, my0, Hm, sx, sy, dx_px=cx0, dy_px=cy0)
        texto = " ".join(palavras).strip()
        if not texto:
            continue
        if _texto_contido(texto, existente):
            continue  # já está no corpo: não duplica (nem embute)
        linhas_pag += linhas
        blocos.append((texto, sum(confs) / len(confs)))
    if linhas_pag:
        m_inv = _inverter_matriz(_ctm_residual(page)) or I
        camada = ([b"q",
                   ("%.6f %.6f %.6f %.6f %.4f %.4f cm" % m_inv).encode("latin-1"),
                   b"BT", b"3 Tr"] + linhas_pag + [b"ET", b"Q"])
        _garantir_fonte(pdf, page, "/FOCR")
        page.contents_add(pdf.make_stream(b"\n".join(camada)), prepend=False)
    return blocos
```

Em `embutir_ocr`: docstring atualizado; `info = {}` no início; o `if _texto_e_aproveitavel(existente): continue` vira:

```python
            manuscrito = _pagina_manuscrita(page, existente)
            if _texto_e_aproveitavel(existente):
                # v2.8: a página TEM corpo de texto, mas pode conter prints/
                # documentos como imagens embutidas — OCR por região nelas.
                try:
                    blocos = _ocr_imagens_embutidas(
                        pdf, page, doc[i], lang, cfg_ocr, existente)
                except Exception as e:
                    print(f"   [aviso] OCR de imagens da pag {i + 1}"
                          f" falhou: {e}")
                    blocos = []
                if blocos:
                    print(f"   OCR de imagem embutida na pagina {i + 1}"
                          f" ({len(blocos)} bloco(s))...", flush=True)
                    n_ocr += 1
                if blocos or manuscrito:
                    info[i] = {"blocos": blocos, "manuscrito": manuscrito}
                continue
            if manuscrito:
                info[i] = {"blocos": [], "manuscrito": True}
```

O restante do fluxo de página inteira continua igual (já refatorado na Task 3). No final: `return n_ocr, info` (e o `pdf.save` continua condicionado a `n_ocr`).

Chamadores:
- `main()`: `n_ocr, info_ocr = embutir_ocr(destino, lang, cfg)` (com `info_ocr = {}` antes do `if args.ocr`), e `exportar_md(parte, md, offset=offset, total=total_pag, info_ocr=info_ocr)`.
- `gui.py` Worker: idem (`info_ocr = {}` por arquivo; `core.embutir_ocr` → tupla; repassa a `core.exportar_md`).

- [ ] **Step 3: Rodar testes**

Run: `python -m pytest tests -q` — Expected: PASS (integração inclusa).

- [ ] **Step 4: Validação quantitativa e visual (os 4 PDFs do spec)**

```powershell
foreach ($f in @("exemplo 1.pdf", "exemplo2.pdf", "exemplo3.pdf", "exemplo9.pdf")) {
  python limpa_pdf_mpsc.py $f --sem-cabecalho --md --ocr --saida "$env:TEMP\lp_t4"
}
```

Conferir (antes/depois — o "antes" é o .md da Task 2 sem `--ocr`):
- exemplo 1/2/3: o `.md` contém `> **[Texto extraído de imagem` com o texto dos prints; abrir o PDF de saída e SELECIONAR texto sobre um print.
- exemplo9: `.md` com `> **[Documento manuscrito — OCR de baixa confiança, revisar no original]**`.
- Nenhum bloco vindo do logo do MPSC (fração 0.014 excluída).
Registrar contagem de chars extraídos por página antes/depois no resumo da task.

- [ ] **Step 5: Commit**

```bash
git add limpa_pdf_mpsc.py gui.py tests/test_ocr_regioes.py
git commit -m "feat: v2.8 — OCR de imagens embutidas (prints/manuscritos) com blocos no .md"
```

---

### Task 5: remover completamente os avisos de tabela/imagem

**Files:**
- Modify: `limpa_pdf_mpsc.py` (apagar `_detectar_tabelas_imagens`, `_texto_aviso`, `IMG_EMBUTIDA_FRAC`, flag `--sem-avisos-tabela-imagem`)
- Modify: `gui.py` (apagar chamada remanescente, se houver, e menções no docstring)

- [ ] **Step 1: Apagar**

- Funções `_detectar_tabelas_imagens` e `_texto_aviso` inteiras; constante `IMG_EMBUTIDA_FRAC` (só era usada ali). MANTER `IMG_PAGINA_FRAC` (usada na limpeza e no filtro de região).
- Em `main()`: o `ap.add_argument("--sem-avisos-tabela-imagem", ...)` e qualquer resto de `avisos`.
- Em `gui.py`: docstring do topo (linha do pipeline com `_detectar_tabelas_imagens`) e qualquer chamada remanescente.

- [ ] **Step 2: Verificar que nada referencia**

Run: `grep -rn "avisos\|_detectar_tabelas\|_texto_aviso\|IMG_EMBUTIDA\|sem-avisos" limpa_pdf_mpsc.py gui.py tests` — Expected: nenhuma ocorrência funcional (comentários históricos ok se removidos também).
Run: `python -m pytest tests -q` — Expected: PASS.

- [ ] **Step 3: Fumaça**

Run: `python limpa_pdf_mpsc.py "exemplo3.pdf" --sem-cabecalho --md --saida "%TEMP%\lp_t5"` e conferir que o `.md` NÃO tem `ATENCAO`, `REDE DE SEGURANCA` nem `>> AVISO`.

- [ ] **Step 4: Commit**

```bash
git add limpa_pdf_mpsc.py gui.py
git commit -m "feat: v2.8 — remover avisos de tabela/imagem do fluxo (conteúdo agora é extraído)"
```

---

### Task 6: GUI — OCR marcado por padrão e rótulos .md

**Files:**
- Modify: `gui.py`

- [ ] **Step 1: Alterações**

- `self.chk_ocr.setChecked(True)` logo após criar o checkbox (OCR é essencial à finalidade de extração).
- Rótulo do `chk_md` (renomeado na Task 2): `"Gerar arquivo de texto (.md) para colar na IA"`.
- Demais checkboxes inalteradas.

- [ ] **Step 2: Verificar**

Run: `python -m pytest tests -q` — Expected: PASS.
Run: `python -c "import sys; from PySide6.QtWidgets import QApplication; import gui; app=QApplication(sys.argv); w=gui.JanelaPrincipal(); assert w.chk_ocr.isChecked(); assert '.md' in w.chk_md.text(); print('ok')"` — Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add gui.py
git commit -m "feat: v2.8 — OCR ligado por padrão na GUI; rótulos .md"
```

---

### Task 7: `dividir_pdf` por TAMANHO em MB (crescer-gravar-medir)

**Files:**
- Modify: `limpa_pdf_mpsc.py` (`dividir_pdf(caminho, max_mb)`, `_salvar_bloco`, `MAX_MB_PARTE`, `DIV_MARGEM_SEGURANCA`; CLI `--max-mb`; remove `MAX_PAGINAS`)
- Modify: `gui.py` (spin em MB)
- Modify: `tests/test_worker.py` (chave `max_pag` → `max_mb`; `mock_core.MAX_PAGINAS` → `MAX_MB_PARTE`)
- Test: `tests/test_dividir_mb.py` (novo)

**Interfaces:**
- Produces: `dividir_pdf(caminho: Path, max_mb: float) -> list[tuple[Path, int]]` (mesmo formato de retorno: `(arquivo, offset_1based)`; `max_mb <= 0` = não dividir). Constantes `MAX_MB_PARTE = 100`, `DIV_MARGEM_SEGURANCA = 0.90`.
- Consumes: nada novo. GUI/CLI passam `max_mb`.

- [ ] **Step 1: Testes que falham**

Criar `tests/test_dividir_mb.py`:

```python
import os
import pikepdf
import pytest
from pathlib import Path

import limpa_pdf_mpsc as core


def _pdf_pesado(path: Path, pesos_kb: list[int]):
    """PDF sintético: cada página referencia um stream de bytes ALEATÓRIOS
    (incompressíveis) do peso pedido — simula páginas escaneadas densas."""
    pdf = pikepdf.new()
    for n, kb in enumerate(pesos_kb):
        page = pdf.add_blank_page(page_size=(612, 792))
        img = pdf.make_stream(os.urandom(kb * 1024))
        img.Type = pikepdf.Name.XObject
        img.Subtype = pikepdf.Name.Image
        img.Width = 1
        img.Height = 1
        img.ColorSpace = pikepdf.Name.DeviceGray
        img.BitsPerComponent = 8
        page.Resources = pikepdf.Dictionary(
            XObject=pikepdf.Dictionary(**{f"Im{n}": img}))
        page.Contents = pdf.make_stream(f"q /Im{n} Do Q".encode())
    pdf.save(path)


def _total_paginas(paths):
    tot = 0
    for p in paths:
        with pikepdf.open(p) as pdf:
            tot += len(pdf.pages)
    return tot


def test_divide_por_mb_sem_perder_paginas(tmp_path):
    alvo = tmp_path / "grande.pdf"
    _pdf_pesado(alvo, [200] * 15)          # ~3 MB total
    partes = core.dividir_pdf(alvo, 1)     # limite 1 MB (efetivo 0.9 MB)
    limite = int(1 * 1024 * 1024 * core.DIV_MARGEM_SEGURANCA)
    assert len(partes) > 1
    assert not alvo.exists()               # original substituído
    assert _total_paginas([p for p, _ in partes]) == 15   # NENHUMA página some
    for p, _off in partes:
        assert p.stat().st_size <= limite  # nenhuma parte acima do limite
    # offsets contínuos: offset da parte k = 1 + páginas das partes anteriores
    esperado = 1
    for p, off in partes:
        assert off == esperado
        with pikepdf.open(p) as pdf:
            esperado += len(pdf.pages)


def test_pagina_gigante_mantida_inteira(tmp_path, capsys):
    alvo = tmp_path / "gigante.pdf"
    _pdf_pesado(alvo, [100, 2000, 100])    # página 2 sozinha > 1 MB
    partes = core.dividir_pdf(alvo, 1)
    assert _total_paginas([p for p, _ in partes]) == 3
    saida = capsys.readouterr().out
    assert "mantida inteira" in saida      # avisou, não fracionou nem perdeu


def test_max_mb_zero_nao_divide(tmp_path):
    alvo = tmp_path / "peq.pdf"
    _pdf_pesado(alvo, [50, 50])
    assert core.dividir_pdf(alvo, 0) == [(alvo, 1)]
    assert alvo.exists()


def test_arquivo_menor_que_limite_nao_divide(tmp_path):
    alvo = tmp_path / "cabe.pdf"
    _pdf_pesado(alvo, [50, 50])
    assert core.dividir_pdf(alvo, 100) == [(alvo, 1)]
    assert alvo.exists()
```

Run: `python -m pytest tests/test_dividir_mb.py -q` — Expected: FAIL (assinatura antiga divide por páginas).

- [ ] **Step 2: Implementar**

Substituir `MAX_PAGINAS = 150` por:

```python
# Divisão por TAMANHO (v2.8): o gargalo do Copilot/IPED é o tamanho do
# arquivo, não a contagem de páginas (uma página escaneada pesa MUITAS vezes
# mais que uma só-texto). Partes de até MAX_MB_PARTE megabytes; 0 = não
# dividir. A margem deixa o arquivo final confortavelmente abaixo do teto.
MAX_MB_PARTE = 100          # tamanho máximo de cada parte, em MB
DIV_MARGEM_SEGURANCA = 0.90 # limite efetivo = max_mb * margem (folga)
```

Substituir `dividir_pdf` por:

```python
def _salvar_bloco(pdf, ini: int, fim: int, destino: Path) -> int:
    """Grava as páginas [ini, fim) num novo PDF e devolve o tamanho REAL em
    bytes do arquivo salvo (mesma compressão do fluxo normal)."""
    novo = pikepdf.new()
    for p in pdf.pages[ini:fim]:
        novo.pages.append(p)
    novo.save(destino, compress_streams=True,
              object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return destino.stat().st_size


def dividir_pdf(caminho: Path, max_mb: float):
    """Divide o PDF em partes de até 'max_mb' MB (tamanho REAL do arquivo).

    Estratégia CRESCER-GRAVAR-MEDIR: o bloco cresce página a página e, a cada
    candidata, é GRAVADO em disco e MEDIDO — nada de estimar MB/página (o
    peso não é linear: estimativas por stream subestimam 6-34%). Se a página
    candidata estoura o limite, ela NÃO entra e vira o início da próxima
    parte. REGRA INVIOLÁVEL: nenhuma página é perdida nem fracionada — uma
    página que sozinha excede o limite sai numa parte própria, com aviso.

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
                partes.append((destino, i + 1))
                i = fim
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
```

CLI em `main()` — trocar `--max-paginas` por:

```python
    ap.add_argument("--max-mb", type=float, default=MAX_MB_PARTE,
                    help=f"divide o PDF em partes de até N megabytes (padrão"
                         f" {MAX_MB_PARTE} MB; use 0 para não dividir)")
```

e `partes = dividir_pdf(destino, args.max_mb)`.

GUI — em `_montar()`:

```python
        self.chk_div = QCheckBox("Dividir PDFs grandes em partes de no máximo")
        self.chk_div.setChecked(True)
        self.spin_mb = QSpinBox()
        self.spin_mb.setRange(5, 5000)
        self.spin_mb.setValue(core.MAX_MB_PARTE)
        self.spin_mb.setSuffix(" MB")
        self.chk_div.toggled.connect(self.spin_mb.setEnabled)
```

(renomear `self.spin_pag` → `self.spin_mb` em todos os usos). Em `_iniciar()`: `"max_mb": self.spin_mb.value(),` e no Worker: `max_mb = op["max_mb"] if op["dividir"] else 0` + `core.dividir_pdf(destino, max_mb)`.

`tests/test_worker.py`: `"max_pag": 0` → `"max_mb": 0`; `mock_core.MAX_PAGINAS = 150` → `mock_core.MAX_MB_PARTE = 100`.

- [ ] **Step 3: Rodar e ver passar**

Run: `python -m pytest tests -q` — Expected: PASS.

- [ ] **Step 4: Validação de fluxo completo (Tarefas 2+5 juntas, pesos mistos)**

Montar um PDF real misto (texto + escaneado) e rodar o pipeline inteiro com limite baixo para forçar divisão:

```powershell
python - <<'EOF'
import pikepdf
pdf = pikepdf.open("exemplo2.pdf")
for f in ["exemplo3.pdf", "exemplos/exemplo4.pdf", "exemplos/exemplo5.pdf",
          "exemplos/exemplo6.pdf", "exemplos/exemplo7.pdf"]:
    with pikepdf.open(f) as p2:
        pdf.pages.extend(p2.pages)
pdf.save("$env:TEMP/misto.pdf")
EOF
python limpa_pdf_mpsc.py "$env:TEMP\misto.pdf" --sem-cabecalho --md --ocr --max-mb 1
```

Conferir: (a) nenhuma `_parteNN.pdf` acima de 1 MB (exceto aviso de página-gigante); (b) soma das páginas das partes = total do original; (c) `## Página N` contínuo entre os `.md` das partes; (d) divisão rodou DEPOIS do OCR (o peso extra da camada foi medido, não estimado).

- [ ] **Step 5: Commit**

```bash
git add limpa_pdf_mpsc.py gui.py tests/test_dividir_mb.py tests/test_worker.py
git commit -m "feat: v2.8 — dividir por tamanho real em MB (crescer-gravar-medir)"
```

---

### Task 8: documentação v2.8

**Files:**
- Modify: `limpa_pdf_mpsc.py` (docstring do módulo: header v2.8 com "Novidades da v2.8", uso `--md --ocr --max-mb`)
- Modify: `CLAUDE.md` (§2 estado v2.8; §3 assinaturas novas: `exportar_md`, `embutir_ocr -> (int, dict)`, `dividir_pdf(caminho, max_mb)`, remoção de `_detectar_tabelas_imagens`; §4 nota do OCR de região; §8 opções da GUI: OCR padrão ligado, campo MB, .md; §9 roadmap; §10 sem mudanças de deps)
- Modify: `gui.py` (docstring do topo já tocado nas tasks; conferir consistência)

- [ ] **Step 1: Docstring do módulo** — nova seção no topo:

```
Novidades da v2.8:
  - SAÍDA SEMPRE EM MARKDOWN (.md): título com metadados (nº do processo,
    unidade, total de páginas), "## Página N de TOTAL" contínuo entre partes,
    peças processuais como "### <PEÇA>" (PECA_ROTULOS, detecção conservadora)
    e tabelas Markdown apenas quando reais (filtro 2x2). Avisos de tabela/
    imagem REMOVIDOS: o conteúdo das imagens agora é extraído ativamente.
  - OCR DE IMAGENS EMBUTIDAS: páginas com texto de corpo E prints/documentos
    anexados como imagem (prova!) agora passam por OCR POR REGIÃO — texto
    invisível selecionável no PDF + bloco marcado no .md, com deduplicação
    tolerante contra o corpo. Páginas manuscritas: OCR best-effort com
    marcação explícita de baixa confiança.
  - DIVISÃO POR TAMANHO (MB): partes de até --max-mb megabytes (padrão 100),
    medindo o tamanho REAL gravado (crescer-gravar-medir) — nunca estima,
    nunca perde página; página que sozinha excede o limite sai inteira com
    aviso.
```

Atualizar a linha de versão (`v2.7` → `v2.8`) e o exemplo de uso: `python limpa_pdf_mpsc.py "C:\pasta" --sem-cabecalho --md --ocr`.

- [ ] **Step 2: CLAUDE.md** — atualizar §2 (estado v2.8), §3 (assinaturas exatas acima), §4 (acrescentar a armadilha: "camada invisível de OCR aparece no FIM do texto extraído — exportar_md remove por sufixo tolerante"), §8 (OCR padrão ligado; campo "no máximo [100] MB"; .md), §9 (marcar v2.8 feita).

- [ ] **Step 3: Verificação final completa**

Run: `python -m pytest tests -q` — Expected: PASS total.
Run: fumaça GUI (`python gui.py`, fechar) e CLI (`python limpa_pdf_mpsc.py "exemplo 1.pdf" --sem-cabecalho --md --ocr`).

- [ ] **Step 4: Commit + reportar pendência**

```bash
git add limpa_pdf_mpsc.py CLAUDE.md gui.py
git commit -m "docs: v2.8 — docstring, CLAUDE.md e rótulos atualizados"
```

Reportar ao usuário: `LEIA-ME.txt` e a Proposta Técnica (.docx) não existem no repositório — só os PDFs gerados (`Limpa_PDF_Manual_do_Usuario.pdf`, `Apresenta LimpaPDF.pdf`), que não são editáveis por aqui. Pedir os fontes (.docx/.txt) ou autorização para recriar.

---

## Self-Review (executado na escrita)

- **Cobertura do spec:** T1 (.md, peças, tabelas, main/GUI/bat, proteção sem-texto) → Tasks 1-2; T2 (OCR região, dedup, confiança, manuscrito, validação nos 4 PDFs) → Tasks 3-4; T3 (avisos fora) → Tasks 1 (não escreve) + 5 (apaga máquina); T4 (OCR default, rótulos) → Task 6; T5 (MB, crescer-gravar-medir, página-gigante, CLI/GUI/bat) → Task 7; docs → Task 8. LEIA-ME/Proposta: inexistentes no repo, reportar (não inventar).
- **Tipos consistentes:** `info_ocr = {int: {"blocos": [(str, float)], "manuscrito": bool}}` igual em `embutir_ocr` (produz) e `exportar_md` (consome); `dividir_pdf` mantém retorno `[(Path, int)]`; `IMG_OCR_CONF_BAIXA` definida na Task 1 e usada só lá.
- **Sem placeholders:** todo código está literal; comandos com saída esperada.
