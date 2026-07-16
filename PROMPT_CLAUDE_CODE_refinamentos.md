# PROMPT PARA O CLAUDE CODE — Limpa PDF MPSC: 3 refinamentos

## 0. Contexto e regras do jogo

Estou refinando o **Limpa PDF MPSC** (limpeza + OCR + exportação `.md` de processos exportados do SIG/Softplan). O programa **já funciona bem** — este trabalho é de *cirurgia*, não de reforma.

**Regras inegociáveis:**

1. **Não quebre o que funciona.** A remoção de **cabeçalho/rodapé** e da **assinatura digital vertical na lateral** está calibrada e aprovada. Ela deve continuar funcionando **exatamente igual**.
2. **Nunca troque qualidade por velocidade.** Se uma otimização puder degradar o OCR (mesmo que pouco), **descarte-a** e mantenha o comportamento atual. Prefiro lento e correto.
3. **Diagnostique antes de corrigir.** Nada de ajustar limiar "no chute". Toda mudança de constante precisa ser justificada por uma medição feita nos PDFs de exemplo.
4. **Prototipe isolado, valide, só então aplique ao arquivo principal.** Mostre-me o diff e o porquê antes de consolidar.
5. Não renomeie o que já existe nem refatore fora do escopo. Constantes novas vão para o topo do módulo, com nome falante e comentário.
6. Os nomes de funções citados abaixo vêm da versão que analisei. **Confirme por `grep` no código vivo** antes de aplicar — pode ter mudado.

---

## 1. TAREFA A — "Apagou demais": parar de destruir certidões e tabelas

### A.0 O problema

Na pasta `exemplos/` estão:

- `Apagou demais ORIGINAL.pdf`
- `Apagou demais LIMPO.pdf`

O LIMPO perdeu conteúdo legítimo do miolo: **informações de uma certidão** e **dados de tabelas**. Isso é o pior tipo de defeito possível neste programa: perda silenciosa de prova.

**Diretriz:** *a rigor, não apagar tabela nenhuma.* O foco da limpeza deve ser **cabeçalho, rodapé, carimbo CÓPIA e assinatura digital lateral** — nada mais.

### A.1 Diagnóstico obrigatório (fazer ANTES de qualquer correção)

Hoje a função `reescrever()` decide `drop = True` em ~10 pontos diferentes, sem registrar *qual regra* disparou. Sem isso, corrigir é adivinhação.

1. Refatore `reescrever()` para produzir, em vez de um `bool drop`, um **motivo** (string) ou `None`. Motivos possíveis (nomes sugeridos):
   `assinatura_rotacionada`, `assinatura_vetorial`, `carimbo_copia`, `boiler_texto`, `boiler_imagem`, `boiler_path`, `cluster_topo`, `corte_topo`, `corte_base`, `faixa_base_vetorial`, `faixa_fixa_topo_txt`, `faixa_fixa_base_txt`, `canto_direito`, `glifo_orfao`.
2. Crie `auditoria_limpeza.py` com um modo `--auditar` que roda a limpeza **sem salvar** e emite `RELATORIO_APAGOU_DEMAIS.md` contendo, para `Apagou demais ORIGINAL.pdf`:
   - Tabela por página: caracteres removidos por motivo, e % do texto da página que cada motivo levou.
   - **O texto efetivamente removido** (trechos), agrupado por motivo — é aqui que a certidão vai aparecer.
   - Ranking global: qual motivo é responsável pela maior perda.
3. Faça também um diff do texto extraído `ORIGINAL` × `LIMPO` (pypdfium2), listando as linhas perdidas e em que página estavam. Cruze com o item 2.

**Só depois desse relatório, corrija.** Se alguma hipótese abaixo não se confirmar, diga isso e **não mexa** naquela regra.

### A.2 Hipóteses ranqueadas (verifique nesta ordem)

**H1 — `_eh_regua()` confunde borda de tabela com a régua do cabeçalho. (principal suspeita)**

```python
def _eh_regua(bbox, W, H):
    w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
    if w < 0.45 * W or h > 3.5: return None
    if bbox[1] >= H * 0.72: return "topo"     # <-- 0.72 !!
    if bbox[3] <= H * 0.18: return "base"
```

Qualquer linha horizontal com **≥45% da largura** e **≤3,5 pt** de espessura acima de **72% da altura** vira "régua de topo". A borda superior de uma tabela satisfaz isso trivialmente. E `reescrever()` apaga **tudo que estiver acima do corte** (`bbox[1] >= cut_topo - 1` para texto; `bbox[3] >= cut_topo - 2` para path/imagem). Resultado: título/preâmbulo da certidão e o cabeçalho da tabela desaparecem.
O mesmo vale para o lado de baixo (`0.18`), que come as últimas linhas.
Em documentos longos, `analisar()` ainda propaga esse corte por repetição (`reguas[g][(lado, round(y/6))]`): uma tabela que se repete em ≥25% das páginas vira "régua" em todas elas.

**H2 — a normalização de dígitos transforma dados de tabela em "boilerplate".**

```python
key = ("T", round(bbox[1]/4), bt_txt)   # bt_txt = norm_txt(...)  dígitos -> '#'
```

`norm_txt()` troca todo dígito por `#`. Numa tabela paginada, a célula `1.234,56` da página 1 e `9.870,00` da página 2 caem no **mesmo y** e viram a **mesma chave** `"#.###,##"`. Repetiu em ≥ `max(3, 25% das páginas)` → classificado como cabeçalho repetido → **apagado**. Isso explica "dados de tabelas" sumindo.
Agrava: a zona de busca é `ZONA_TOPO = 0.30` (30% da altura ≈ 250 pt numa A4 — muito abaixo de qualquer cabeçalho real) e `ZONA_BASE = 0.12`.

**H3 — o laço que "estende o corte de topo" desce pela tabela.**
Em `_corte_regua_pagina()`, o corte desce enquanto houver linhas coladas (`ref - y <= 22`). Linhas de tabela têm espaçamento < 22 pt → o corte pode descer degrau a degrau pela tabela.

**H4 — `boiler_base_P` / `faixas_base`** removem paths repetidos nos 10-12% inferiores: pode estar comendo a borda inferior e a última linha de tabelas que terminam no pé da página.

**H5 — `_faixa_assinatura_vetorial()`** pode capturar uma coluna estreita e densa de tabela junto à margem. **Menos provável** (exige ≥25 glifos, densidade ≥12/100 pt e cobertura ≥55% da altura), mas confirme no relatório.

### A.3 Correções (aplicar apenas as que o diagnóstico confirmar)

**C1 — Zonas de tabela são território protegido.**

- Crie `zonas_tabela(els, W, H)` reaproveitando a lista de elementos **que o pikepdf já parseou** (não use pdfplumber aqui — ver Tarefa C): colete segmentos horizontais finos (altura ≤ 3,5 pt) e verticais finos (largura ≤ 3,5 pt); calcule interseções; considere tabela quando houver **≥2 linhas horizontais e ≥2 linhas verticais** formando pelo menos uma célula fechada (o filtro mínimo 2×2 que já sabemos ser necessário para não gerar falso positivo com texto justificado). Devolva os bboxes das grades, dilatados ~4 pt.
- **Nenhuma regra de remoção pode apagar elemento cujo centro caia dentro de uma zona de tabela**, com **duas exceções**: texto rotacionado (assinatura) e o carimbo CÓPIA.
- Se uma zona de tabela invadir a faixa do cabeçalho, o cabeçalho continua sendo removido **apenas acima** da borda superior da tabela.

**C2 — `_eh_regua()` mais exigente (a régua é solitária; a tabela é uma grade).**
Uma régua de cabeçalho/rodapé deve satisfazer **todas**:
- posição: topo apenas se `bbox[1] >= H * LIM_REGUA_TOPO` e base apenas se `bbox[3] <= H * LIM_REGUA_BASE`. **Meça no acervo** onde fica a régua real do MPSC (rode um script nos PDFs de regressão e imprima o `y/H` de cada régua verdadeira) e fixe os limiares a partir do dado — não do chute. Suspeito que o valor real fique perto de 0,88–0,92 no topo, não 0,72.
- isolamento: **não** existir outra linha horizontal de largura semelhante a menos de ~30 pt (grade de tabela tem linhas paralelas próximas).
- ausência de verticais: **não** existir linha vertical cruzando o span x da régua e se estendendo mais de ~10 pt para além dela.
- não estar dentro de uma zona de tabela (C1).

**C3 — Boilerplate de texto não pode comer dado.**
- **Nunca** classificar como boilerplate um texto cuja forma normalizada seja composta só de `#`, pontuação, moeda e espaço (`#.###,##`, `##/##/####`, `r$ #.###,##`, `- #`, etc.). Isso é **dado**, não cabeçalho.
- Trocar a zona de candidatura de boilerplate de **fração da página** para **faixa em pontos**, medida no acervo: algo como `BOILER_TOPO_PT` e `BOILER_BASE_PT` (ordem de 90–120 pt no topo, 70–90 pt na base). 30% da altura é largo demais.
- Manter `FRACAO_REPETICAO` como está.

**C4 — Trava no laço de extensão do corte.**
`cut_topo` nunca pode descer abaixo de `H - LIMITE_CORTE_TOPO_PT` (constante nova, calibrada) nem entrar numa zona de tabela. Idem, espelhado, para `cut_base`.

**C5 — Rede de segurança: rollback por página (implementar sempre, mesmo que as outras correções resolvam).**
Depois de reescrever cada página, compare a quantidade de caracteres de texto extraível **antes × depois**. Se a remoção passar de `LIMITE_PERDA_PAGINA` (comece em **35%** dos caracteres da página), **descarte a reescrita e mantenha a página original**, registrando no log: `[protecao] pag N: remocao excessiva (X%) — pagina mantida intacta`. Ao final, informe quantas páginas foram protegidas.
Justificativa: uma página normal só perde cabeçalho, rodapé e assinatura — algo entre 5% e 20% dos caracteres. Perder 35%+ é sintoma de que uma regra geométrica escorregou. Essa trava torna a falha "apagou demais" **estruturalmente impossível** de repetir, mesmo que uma regra nova falhe no futuro.

### A.4 O que NÃO tocar

- Regra da **assinatura digital rotacionada** (`rot` → drop): intocada.
- `_faixa_assinatura_vetorial()` e suas constantes (`LARG_COL`, `DENS_MIN=12`, `COB_MIN=0.55`, mínimo de 25 glifos, margens 0,22/0,78): **intocadas**. Única exceção admissível: aplicar-lhe a guarda de zona de tabela (C1) — e **somente se** a auditoria provar que ela disparou dentro de uma tabela. Se não disparou, não encoste nela.
- Carimbo CÓPIA (`CANTO_X`, `CANTO_Y`): intocado.
- Proteção da imagem de página inteira (`IMG_PAGINA_FRAC`): intocada.

### A.5 Regressão (obrigatória)

Monte `tests/regressao/` com os 2 exemplos + PDFs em que a limpeza **hoje acerta** (vou te fornecer; se não houver, use os que estiverem no repositório e me avise que preciso mandar mais). Crie `verificar_regressao.py` que, para cada PDF, reporta:

| PDF | cabeçalho removido? | rodapé removido? | assinatura lateral removida? | carimbo removido? | % de caracteres do miolo preservados |

Gere um **baseline JSON antes da mudança** e compare depois. **Falha o teste** se: (a) cabeçalho/rodapé/assinatura deixarem de ser removidos em qualquer PDF, ou (b) a preservação do miolo piorar em qualquer PDF.
Critério de sucesso do Tarefa A: **0 linhas do miolo perdidas** em `Apagou demais ORIGINAL.pdf` (certidão e tabelas íntegras) **e** nenhuma regressão nos demais.

---

## 2. TAREFA B — Barra de progresso que informa de verdade

### B.0 O problema

A barra fica em **0% do começo ao fim** quando há **um único PDF** (que é o caso mais comum): o percentual hoje é calculado por *arquivos concluídos / total de arquivos*. Só se mexe com vários arquivos. O usuário fica sem saber se o programa travou ou está trabalhando — e num procedimento grande isso dura horas.

### B.1 O que quero ver

Barra determinada (0–100%) que anda continuamente **dentro de um único arquivo**, mais um painel de estado:

```
[■■■■■■■■■□□□□□□□□□□□]  43%
Arquivo 1/1 · Procedimento_06.2024.00001234-5.pdf
Etapa: OCR — página 137 de 842
Decorrido 08:12 · restam ~11 min
```

### B.2 Implementação

1. **Callback no núcleo.** Toda função pesada (`analisar`, `reescrever`/`limpa_pdf`, `embutir_ocr`, `numerar_paginas`, `dividir_pdf`, `exportar_md`, detecção de tabela/imagem) recebe um parâmetro opcional `progresso=None` e chama `progresso(etapa, feito, total, detalhe="")`. O núcleo **não conhece Qt** — quem adapta para sinal é a GUI.
2. **Pré-passagem de planejamento (`planejar()`).** Antes de processar, para cada arquivo: número de páginas (instantâneo via pypdfium2) e, principalmente, **quantas páginas realmente irão para o OCR** — reaproveite `_texto_e_aproveitavel()` num varrimento rápido de `get_textpage()` (milissegundos por página). Isso dá um **orçamento exato**, e não uma estimativa.
3. **Orçamento ponderado por TEMPO, não por passos.** Monte o total em "unidades de trabalho":
   `total = Σ (n_pag·P_LIMPEZA + n_pag_ocr·P_OCR + n_pag·P_NUMERA + n_pag·P_EXPORT + n_partes·P_DIVIDE)`
   Comece com pesos aproximados (`P_OCR` domina — algo como 30× o custo de uma página de limpeza) e, **depois da Tarefa C, recalibre os pesos com os tempos medidos**, para que a barra seja linear no tempo real. É isso que o usuário percebe como "barra honesta".
4. **ETA.** Média móvel exponencial de segundos por unidade concluída → "restam ~N min". Não mostre ETA nos primeiros ~5% (ruído).
5. **GUI (PySide6).** Worker em `QThread`; sinais `progresso(int pct, str etapa, str detalhe, str eta)`, `log(str)`, `concluido(...)`, `erro(str)`. Nada de `processEvents()`. **Limite a taxa de emissão a ≤10 por segundo** (com OCR paralelo, os eventos chegam em rajada). O percentual **nunca retrocede**; 100% só ao final de tudo.
6. **Botão Cancelar.** `threading.Event` verificado entre páginas; encerra o pool de forma limpa e não deixa PDF pela metade (grave só ao final ou em arquivo temporário renomeado ao concluir).
7. Mantenha o log textual detalhado que já existe — ele é a segunda fonte de confiança do usuário.

> Obs.: o *print* que você mencionou não chegou junto com a mensagem — descrevi o comportamento a partir do que você relatou. Se o layout atual da barra for diferente do que imagino, ajuste sem cerimônia.

---

## 3. TAREFA C — OCR mais rápido, com qualidade idêntica

### C.0 O problema

Procedimento longo (ex.: 200 MB) leva **horas**. Quero descobrir o que está travando e aliviar **sem perder nada de qualidade**. Se a otimização tiver qualquer custo de precisão de OCR, **ela está vetada**.

### C.1 Etapa 1 — medir (não otimize nada antes disso)

Crie `perfil.py`: roda o pipeline completo num PDF grande representativo (ou numa fatia de 100–200 páginas dele) com cronômetro **por etapa e por página**, mais `cProfile` na etapa de OCR. Entregue `PERFIL_ANTES.md` com a tabela: etapa · tempo total · s/página · % do total.

### C.2 Suspeitos que já identifiquei no código (confirme com o perfil)

1. **`cv2.bilateralFilter(arr, d=5, sigmaColor=40, sigmaSpace=40)` em `_preparar_imagem_ocr()`.** Rodando sobre uma imagem de 400 dpi (~15 megapixels), o filtro bilateral é dos mais caros do OpenCV — provavelmente **1 a 3 s por página**, só nisso. E ele serve apenas para suavizar antes de um **Otsu global**, que é um método de histograma: a suavização quase não muda o limiar escolhido.
2. **OCR estritamente sequencial**, uma página por vez, `pytesseract.image_to_data()` por página. Cada chamada **abre um processo tesseract novo e recarrega o `por.traineddata` do `tessdata_best`** (dezenas de MB). Em 1.000+ páginas isso é 1.000+ inicializações do motor LSTM.
3. **`OMP_THREAD_LIMIT` não definido.** O Tesseract com OpenMP em várias threads costuma ficar **mais lento** que single-thread — e atrapalha qualquer paralelismo por processo.
4. **Render RGB.** `doc[i].render(scale=...).to_pil()` devolve RGB e só depois vira `L`. São 3× mais bytes por página em todas as cópias intermediárias (PIL → numpy → cv2 → PIL).
5. **`_detectar_tabelas_imagens()` chama `pdfplumber.find_tables()` em todas as páginas.** pdfplumber usa pdfminer.six, que é ordens de grandeza mais lento que pypdfium2/pikepdf. Num arquivo de 200 MB com milhares de páginas, isso sozinho pode custar horas.
6. **O arquivo inteiro é reserializado 4–5 vezes:** `limpa_pdf` (save) → `embutir_ocr` (open+save) → `numerar_paginas` (open+open+save) → `dividir_pdf` (open+save) → exportação (open). Cada save de 200 MB com `compress_streams=True, object_stream_mode=generate` não é barato.
7. **Renderização a 400 dpi sobre scans de resolução nativa menor** (muitos scans do SIG são 200–300 dpi): interpolar para 400 quadruplica os pixels sem acrescentar informação.

### C.3 Otimizações candidatas (cada uma passa por um "portão de qualidade")

Ordem sugerida por ganho esperado:

- **O1 — Paralelismo por página (maior ganho, risco zero de qualidade).**
  `ProcessPoolExecutor` com `workers = max(1, cpu_count() - 1)`, cada worker com `OMP_THREAD_LIMIT=1` no ambiente. O worker recebe (caminho do PDF, índice da página, dpi, cfg), abre seu próprio handle pypdfium2, renderiza, pré-processa e devolve o **dict do `image_to_data` + geometria**. A montagem da camada invisível continua **no processo pai** (objetos pikepdf não são serializáveis). O resultado por página é bit a bit o mesmo — só muda a ordem em que ficam prontos.
  **Armadilhas obrigatórias:** `multiprocessing.freeze_support()` no início de `main()` (senão o executável do PyInstaller entra em *fork bomb* no Windows); função do worker no nível do módulo (o Windows usa `spawn`); e teto de workers por RAM (cada worker segura uma imagem de ~15 MP: `workers = min(cpu-1, max(1, RAM_GB // 2))`). Exponha `--workers N` (padrão: automático) na CLI e na GUI.
- **O2 — Otsu barato, binarização idêntica.**
  Calcule o **limiar** de Otsu numa cópia reduzida (ex.: 1/4 da escala, opcionalmente com o filtro bilateral aplicado *nela*, que aí custa quase nada) e depois aplique **esse limiar escalar** à imagem em resolução plena (`cv2.threshold(arr, limiar, 255, THRESH_BINARY)`). O binário resultante é essencialmente o mesmo, a um custo desprezível.
  *Portão:* imagem binária ≥99,9% de pixels idênticos **ou** texto de OCR idêntico numa amostra de 30 páginas. Se não passar, mantenha o `bilateralFilter` como está.
- **O3 — Render direto em tons de cinza** (`render(scale=..., grayscale=True)`): menos memória, menos cópias.
  *Portão:* texto de OCR idêntico na amostra.
- **O4 — Pular páginas em branco** antes do Tesseract (média de pixels ≈ 255 e desvio ≈ 0 → nada a ler). Risco zero, ganho real em procedimentos com muitas folhas separadoras.
- **O5 — Detecção de tabela/imagem sem pdfplumber.** Reaproveite `zonas_tabela()` da Tarefa A (que sai de graça do parse do pikepdf que já fazemos) e elimine o `find_tables()` do pdfplumber. Mata dois coelhos: some um gargalo pesado **e** a detecção passa a ser a mesma usada na proteção contra remoção.
- **O6 — Um save por arquivo.** Encadeie limpeza → OCR → numeração no **mesmo `pikepdf.Document` em memória** e grave uma única vez; só então divida. Elimina 3 reserializações completas de 200 MB.
- **O7 — Evitar OCR duplicado.** Se a página inteira já foi ocerizada, não reprocessar regiões de imagem contidas nela (dedup por IoU ≥ 0,9 com a área já coberta).
- **O8 — DPI consciente da resolução nativa** *(só se os portões acima não bastarem — este é o mais arriscado)*. Calcule o dpi efetivo da imagem embutida; renderizar a 400 dpi um scan de 200 dpi só interpola. **Mas** o Tesseract às vezes lê melhor material ampliado — então **nunca abaixo de 300 dpi**, e adote **apenas** se o portão de qualidade der resultado igual ou melhor. Na dúvida, **fica em 400**.
- **O9 (opcional, avaliar)** — Uma única invocação do Tesseract para um lote de páginas via *file list* (carrega o modelo uma vez só) ou `tesserocr` (API C, mantém o motor carregado). Ganho real, mas mexe em empacotamento/PyInstaller. **Só investigue se O1 não bastar**, e valide que o `.exe` continua gerando corretamente.

### C.4 Portão de qualidade (protocolo obrigatório)

Amostra fixa de **≥30 páginas** cobrindo: página nativa de texto, scan limpo, scan sujo, **manuscrito**, **print de WhatsApp**, e página com tabela.
Para cada otimização, compare ANTES × DEPOIS:

- total de caracteres reconhecidos: `depois >= antes * 0,999`
- confiança média do Tesseract: `depois >= antes - 0,5`
- diff palavra a palavra: sem perda sistemática

**Qualquer otimização que não passe é descartada.** Entregue `PERFIL_DEPOIS.md` com a tabela antes/depois de tempo **e** de qualidade, lado a lado.

**Meta:** reduzir o tempo de parede em **≥3×** no caso de 200 MB, com texto de OCR igual ou melhor. Se só der para reduzir 2× sem tocar na qualidade, ótimo — 2× é o resultado.

---

## 4. Entregáveis

1. Código alterado (com diff explicado antes de consolidar no arquivo principal).
2. `auditoria_limpeza.py` + `RELATORIO_APAGOU_DEMAIS.md`.
3. `tests/regressao/` + `verificar_regressao.py` + baseline JSON.
4. `perfil.py` + `PERFIL_ANTES.md` + `PERFIL_DEPOIS.md`.
5. Changelog no *docstring* do módulo (nova versão), no mesmo estilo das anteriores.
6. Constantes novas no topo do módulo, nomeadas e comentadas (ex.: `LIM_REGUA_TOPO`, `BOILER_TOPO_PT`, `LIMITE_PERDA_PAGINA`, `OCR_WORKERS`).

## 5. Critérios de aceite

- [ ] Certidão e dados de tabela de `Apagou demais ORIGINAL.pdf` **integralmente preservados** no novo LIMPO.
- [ ] Cabeçalho, rodapé, carimbo e **assinatura digital lateral continuam sendo removidos** em 100% dos PDFs de regressão (sem piora).
- [ ] Rede de segurança de rollback por página ativa e reportada no log.
- [ ] Barra de progresso anda continuamente com **1 arquivo**, mostrando etapa, página X/Y e ETA; botão Cancelar funcional.
- [ ] Ganho de tempo medido e documentado, **com qualidade de OCR igual ou superior** (portão de qualidade aprovado).
- [ ] O `.exe` (PyInstaller) continua funcionando — atenção especial ao `freeze_support()` do multiprocessing no Windows.

## 6. Ordem de execução

**A (diagnóstico) → A (correção + regressão) → C (perfil) → C (otimizações com portão) → B (progresso, com pesos calibrados pelos tempos medidos em C).**

A Tarefa A é a mais urgente: enquanto ela não estiver resolvida, o programa está apagando prova.
