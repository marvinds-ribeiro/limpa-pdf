# CLAUDE.md — Limpa PDF (MPSC)

> Contexto persistente do projeto para o Claude Code. Leia este arquivo antes de
> qualquer alteração. Ele descreve o propósito, as decisões já tomadas, as
> armadilhas dos PDFs do SIG e os princípios que não devem ser violados.

---

## 1. O que é o projeto

**Limpa PDF** é uma utilidade local que limpa PDFs de procedimentos exportados do
SIG (Softplan), o sistema de gestão de processos do **Ministério Público de Santa
Catarina (MPSC)**. O objetivo é preparar esses documentos para análise por IA
(Microsoft Copilot 365, IPED e afins): o PDF bruto do SIG vem cheio de "moldura"
(assinatura digital repetida em toda página, carimbo CÓPIA, cabeçalhos/rodapés)
que desperdiça janela de contexto e tokens, e atrapalha a leitura humana e
automática.

**Princípio operacional central: tudo roda 100% local e offline.** Nada é enviado
para a internet, não há login, não há custo. Para uma instituição que lida com
sigilo bancário, fiscal e telemático, isso é requisito, não conveniência. Qualquer
mudança que introduza dependência de rede em tempo de uso é inaceitável.

Distribuição: interna ao MPSC, via **ZenWorks** (sistema de gestão de TI). A
autorização de componentes (Python, Tesseract) passa pela **COTEC**.

---

## 2. Estado atual e arquivos

A lógica de limpeza está madura (~1.549 linhas, validada em produção) e já
UNIFICADA numa **base única v2.6** (`limpa_pdf_mpsc.py`). O merge dos antigos
`_PAGINADO` (v2.5, paginação) e `_OCR` (v2.4, OCR de qualidade) JÁ ESTÁ FEITO —
ver MERGE.md, que agora é registro histórico, não tarefa pendente. A v2.6 tem:

- **Paginação contínua** (`numerar_paginas`, rótulo `[Pagina N de TOTAL]` no canto
  superior direito; `dividir_pdf` retorna `(arquivo, offset)`; `exportar_txt` com
  `offset` → cabeçalho `===== Pagina N =====` contínuo entre partes). Flag
  `--sem-numero`.
- **OCR de alta precisão**: `_preparar_imagem_ocr` (OpenCV/Otsu, fallback Pillow),
  render a **400 DPI** (`OCR_DPI`), `--oem 1 --psm 6`, `_normalizar_ocr`
  (correção ordinal→letra com guardas), e cap de render `OCR_MAX_LADO_PX = 5000`
  para mediabox gigante.
- **Detecção de camada de texto corrompida** (era pendência): mede fração
  alfanumérica × controle/PUA; se a página é majoritariamente lixo (sem
  `/ToUnicode`, PUA), remove a camada podre e força o OCR, em vez de despejar lixo
  no `.txt`.

Lançadores atuais (`.bat`) — a serem **substituídos pela GUI**, não mantidos:
`Limpar_PDFs.bat`, `Limpar_PDFs_com_OCR.bat`, `Limpar_PDFs__pasta_separada_.bat`.
Há também `LEIA-ME.txt` (guia do usuário) e `Proposta_Limpa_PDF_SIG_v2.docx`
(proposta institucional para a Administração Superior).

---

## 3. Funções públicas (a GUI chama estas — não reimplementar a lógica)

A GUI deve importar o módulo e chamar estas funções diretamente, **sem** rodar o
`.bat` nem invocar o Python como subprocesso:

- `limpa_pdf(origem: Path, destino: Path, sem_cabecalho: bool) -> int`
  Limpeza estrutural (assinatura, carimbo, cabeçalho/rodapé). Retorna nº de
  páginas alteradas.
- `embutir_ocr(pdf_path: Path, lang: str, cfg: str) -> int`
  OCR nas páginas SEM camada de texto; insere texto invisível selecionável.
  Requer `_preparar_ocr()` antes, para obter `(lang, cfg)`.
- `numerar_paginas(pdf_path: Path, total: int, inicio: int = 1) -> int`
  Carimbo de paginação contínua. Chamado sobre o PDF INTEIRO, antes de dividir.
- `dividir_pdf(caminho: Path, max_pag: int) -> list[(Path, offset)]`
  Divide em partes de até `max_pag`; offset = 1ª página da parte no documento.
- `exportar_txt(pdf_path, txt_path, avisos=None, offset=1)` — gera o `.txt`.
- `_preparar_ocr() -> (lang, cfg)` — localiza Tesseract e idioma português.
- `_detectar_tabelas_imagens(pdf_path)` — rede de segurança (avisos no `.txt`).

**Ordem do pipeline (replicar o que o `main()` faz hoje):**
1. `limpa_pdf` → 2. `embutir_ocr` (se OCR ligado) → 3. `numerar_paginas` (se
paginação ligada, sobre o PDF inteiro) → 4. `dividir_pdf` → 5. para cada parte,
`_detectar_tabelas_imagens` + `exportar_txt` (se TXT ligado).

---

## 4. Armadilhas dos PDFs do SIG (conhecimento caro — não reaprender na marra)

- **CTM residual:** os PDFs do SIG abrem o content stream com
  `0.75 0 0 -0.75 0 H cm` SEM um `q` isolante. Qualquer camada anexada ao fim do
  stream (OCR, paginação) herda esse CTM e sai distorcida/condensada no topo.
  Fix existente: `_ctm_residual()` mede o residual, `_inverter_matriz()` calcula a
  inversa, e ela é emitida (`cm`) antes do bloco de texto. NÃO remover isso.
- **Camada de texto corrompida:** páginas com encoding de fonte quebrado (sem
  `/ToUnicode`, Unicode em Private Use Area) podem ter `len(texto) >= 20` e enganar
  a checagem que decide pular OCR. Detecção correta: fração alfanumérica < 0.45 ou
  fração de controle/PUA > 0.20 = lixo; a camada corrompida é removida antes do
  overlay de OCR. (Implementado na v2.6.)
- **Imagem de página inteira:** imagens cobrindo ≥80% da página (`IMG_PAGINA_FRAC`)
  são conteúdo escaneado, NUNCA decoração. Nunca removê-las pela lógica de
  cabeçalho/rodapé.
- **Falsos positivos de tabela:** `pdfplumber.find_tables()` lê espaços em branco
  de texto justificado como divisórias de coluna. Filtro mínimo de 2 linhas E 2
  colunas elimina o falso positivo preservando tabelas reais.
- **Tesseract `por`:** na máquina do usuário, `por.traineddata` pode estar na pasta
  `tessdata` do IPED, não na do Tesseract. `_localizar_tessdata_por()` varre vários
  locais antes de tentar baixar — isso é o que garante operação offline.
- **OCR — stack atual de melhor qualidade:** `tessdata_best` + `--oem 1 --psm 6` +
  render 400 DPI + binarização Otsu + `_normalizar_ocr()`.

---

## 5. Princípio inviolável: preservação conservadora de conteúdo

Na dúvida, **NÃO remover**. Falso negativo (deixar um resíduo de moldura) é sempre
preferível a falso positivo (destruir conteúdo legítimo — uma prova, um trecho de
investigação). Vale para assinatura colada ao corpo, marca d'água rasterizada,
imagem grande ao fundo. Esta é a regra que sobrepõe qualquer ajuste de threshold.

**Correção é empírica, não arbitrária.** Quando um caso real sai errado, o método é
diagnosticar a causa-raiz e corrigi-la, não mexer num número até "parar de dar
errado". Cada mudança é prototipada e validada isoladamente (quantitativa e
visualmente) antes de entrar no arquivo principal.

---

## 6. Convenções de código

- **Constantes nomeadas em nível de módulo**, nunca números mágicos:
  `OCR_DPI`, `OCR_MAX_LADO_PX`, `OCR_LIMIAR_BIN`, `OCR_BINARIZAR`, `TAB_MIN_LINHAS`,
  `TAB_MIN_COLUNAS`, `MAX_PAGINAS`, `MAX_PAG_CURTO`, `FAIXA_TOPO_FRAC`,
  `FAIXA_BASE_FRAC`, `ZONA_TOPO`, `ZONA_BASE`, `FRACAO_REPETICAO` etc. Toda
  grandeza ajustável vira constante no topo do módulo, com comentário do efeito.
- **Versionamento explícito** no docstring do módulo (v2.3 → v2.4 → v2.5 → v2.6),
  cada versão com escopo de feature claro.
- **Comunicação técnica precisa, porém acessível** a um programador intermediário.
- Comentários em português; o código já segue esse padrão.

---

## 7. GUI e empacotamento (decisões fechadas)

- **GUI: PySide6 (Qt).** Escolhido pela licença LGPL (adequada a distribuição no
  setor público) e drag-and-drop nativo. Expõe as funções da seção 3.
- **Empacotamento: PyInstaller** congela o app + bibliotecas (pikepdf, pdfplumber,
  pypdfium2, pytesseract, Pillow, **opencv-python-headless**, numpy). Use SEMPRE o
  `headless` do OpenCV — evita conflito de plugin de plataforma Qt com o PySide6.
- **Tesseract embutido no pacote** (executável + DLLs + `por.traineddata` do
  `tessdata_best`), com `pytesseract.tesseract_cmd` apontando para o caminho
  interno. Garante operação 100% offline; sem download na 1ª execução.
- **Instalador: Inno Setup** gera `setup.exe` com suporte a instalação silenciosa
  (`/SILENT`, `/VERYSILENT`) para o ZenWorks. Instalar por máquina (Program Files).
- **Risco conhecido:** PyInstaller + OpenCV + PySide6 costuma gerar conflitos de
  DLL / plugin de plataforma Qt. Reservar tempo para a fase de empacotamento — ela
  costuma dar mais trabalho que a GUI em si.
- **Code signing:** verificar com a COTEC se há certificado para assinar o
  `setup.exe`; executáveis não assinados podem ser bloqueados por
  SmartScreen/política de grupo no ambiente gerenciado.

---

## 8. Especificação da GUI (ponto de partida — iterar a partir daqui)

Design: **simples e limpo**. Janela única, fluxo de cima para baixo. Nada de abas
ou assistentes de múltiplas telas. O objetivo é substituir o "arrastar PDF para o
.bat" por algo que qualquer servidor use sem treinamento.

**Layout da janela (de cima para baixo):**

1. **Título + explicação breve.** Um cabeçalho curto explicando a finalidade, em
   linguagem para leigo. Sugestão de texto (ajustável):
   *"Limpa PDF — prepara procedimentos exportados do SIG para uso em ferramentas de
   inteligência artificial. Remove cabeçalhos e rodapés, apaga a assinatura digital
   da lateral e o carimbo de cópia, e opcionalmente reconhece o texto de páginas
   escaneadas (OCR). Tudo no seu computador, sem enviar nada para a internet."*

2. **Seleção de entrada.** Um botão/área "Selecionar arquivos" que permite escolher
   **ou uma pasta inteira ou um PDF específico** (dois botões — "Selecionar pasta" e
   "Selecionar PDF" — ou um botão com menu). Manter também o drag-and-drop da janela
   como atalho (arrastar pasta/arquivo para dentro), já que é nativo no Qt e
   preserva o gesto a que os usuários estão acostumados. Mostrar o caminho
   selecionado na tela.

3. **Opções (aparecem após selecionar a entrada).** Todas com rótulo claro:
   - **OCR** — checkbox "Reconhecer texto de páginas escaneadas (OCR)". Avisar que
     é mais lento. Padrão: desligado (a maioria dos PDFs do SIG já tem texto).
   - **Paginação** — checkbox "Numerar as páginas (recomendado para citar páginas à
     IA)". Padrão: ligado (espelha o comportamento atual; flag inversa `--sem-numero`).
   - **Dividir PDF** — checkbox "Dividir PDFs grandes em partes" + campo numérico de
     páginas por arquivo, **pré-preenchido com 150** (`MAX_PAGINAS`). Quando
     desmarcado, equivale a `--max-paginas 0` (não dividir).
   - **Gerar .txt** — checkbox "Gerar arquivo de texto (.txt) para colar na IA".
     Padrão: ligado.
   - (Implícito hoje: `--sem-cabecalho` está sempre ligado no fluxo dos `.bat`.
     Manter ligado por padrão; opcionalmente expor como opção avançada.)

4. **Botão "Limpar".** Dispara o processamento.

5. **Progresso.** Barra de progresso + texto de status (ex.: "OCR página 12...",
   "Dividindo...", nome do arquivo atual). O processamento de lotes grandes é
   demorado (OCR ~3-6 s/página), então:
   - **Rodar o processamento numa thread separada** (`QThread`), nunca na thread da
     UI, senão a janela congela.
   - Reportar progresso por sinal/slot do Qt. As funções de núcleo já imprimem
     status (`print(... flush=True)`); avaliar expor um callback de progresso para a
     GUI capturar, em vez de capturar stdout.

6. **Conclusão.** Mensagem de fim com o resumo (arquivos gerados, páginas
   alteradas) e um botão para abrir a pasta de saída.

**Comportamento que NÃO deve mudar:** o original nunca é alterado (gera cópia
limpa); operação offline; pipeline na ordem da seção 3.

---

## 9. Roadmap

- [x] Merge dos dois scripts numa base v2.6 (OCR de qualidade + paginação).
- [x] Detecção de camada de texto corrompida antes do OCR (seção 4).
- [ ] **PRÓXIMO:** Esqueleto da GUI PySide6 (seção 8), com QThread (ver `gui.py`).
- [ ] Empacotamento PyInstaller + Tesseract embutido + Inno Setup (seção 7).
- [ ] Proposta formal à COTEC para autorizar Python + Tesseract via ZenWorks.
- [ ] Inicializar repositório Git (se ainda não estiver).

---

## 10. Ambiente / dependências

- **Bibliotecas:** pikepdf, pdfplumber, pypdfium2, pytesseract, Pillow,
  opencv-python-headless, numpy.
- **OCR:** Tesseract + modelo português `tessdata_best` (`por.traineddata`).
- **GUI:** PySide6.
- **Empacotamento:** PyInstaller, Inno Setup.
- **Deploy:** ZenWorks (TI do MPSC).
- **Sistemas institucionais:** SIG (Softplan), IPED, MorpheusPDF (comparador),
  Microsoft Copilot 365.
