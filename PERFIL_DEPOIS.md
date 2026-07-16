# Perfil de desempenho DEPOIS das otimizações — Tarefa C

**PDF de referência:** `Apagou demais ORIGINAL.pdf` — 81 páginas, 8,5 MB
(o mesmo do `PERFIL_ANTES.md`; medições na mesma máquina, pipeline completo:
limpeza → OCR → numeração → divisão → exportação .md).

## Resultado geral

| | ANTES (v2.8) | DEPOIS (v2.9) | ganho |
| --- | ---: | ---: | ---: |
| **Pipeline completo** | **435,2 s (7,3 min)** | **222,5 s (3,7 min)** | **2,0×** |

## Tempo por etapa (antes × depois)

| etapa | antes (s) | s/pág | depois (s) | s/pág | ganho |
| --- | ---: | ---: | ---: | ---: | ---: |
| limpa_pdf | 40,3 | 0,50 | 45,4 | 0,56 | 0,9× ¹ |
| embutir_ocr | 260,9 | 3,22 | 81,2 | 1,00 | **3,2×** |
| numerar_paginas | 7,1 | 0,09 | 7,5 | 0,09 | = |
| dividir_pdf | 0,0 | — | 0,0 | — | = |
| exportar_md | 126,9 | 1,57 | 88,4 | 1,09 | 1,4× ² |

¹ A limpeza ficou ~5 s mais lenta de propósito: é o custo das proteções da
Tarefa A (zonas de tabela + rollback por página, que extrai o texto antes e
depois da reescrita). Preservar prova > velocidade.

² O `find_tables` (pdfminer) caiu de 81 para **31 páginas** — a varredura
barata `_paginas_com_grade` (parse pikepdf) só o libera onde existe grade
vetorial de verdade. Neste PDF, 31 páginas TÊM grade (certidões e recibos com
caixa traçada — as mesmas protegidas pelas `zonas_tabela`); o custo restante é
trabalho legítimo. Em PDFs 100% escaneados (o caso do procedimento de 200 MB),
o filtro zera o pdfplumber e o ganho é muito maior que o 1,4× deste exemplo.

## Otimizações aplicadas × descartadas

| otimização | decisão | motivo |
| --- | --- | --- |
| O1 — OCR paralelo por página (`ProcessPoolExecutor`, `OCR_WORKERS`, `OMP_THREAD_LIMIT=1` por worker) | **APLICADA** | resultado por página idêntico ao sequencial; só muda a ordem de conclusão |
| O4 — pular páginas em branco antes do Tesseract | **APLICADA** | risco zero (média ≈ 255 e desvio ≈ 0 → nada a ler) |
| O5 — `find_tables` só em páginas com grade vetorial (`_paginas_com_grade`) | **APLICADA** | saída idêntica (o find_tables por linhas só acha tabela onde há grade) |
| O2 — Otsu calculado em cópia reduzida | **REPROVADA no portão** | binarização divergiu; qualidade nunca se troca por velocidade |
| O3 — render direto em tons de cinza (`OCR_RENDER_CINZA = False`) | **REPROVADA no portão** | texto de OCR divergiu na amostra |

## Portão de qualidade (C.4) — APROVADO

Amostra de 30 páginas espaçadas do PDF de referência, caminho v2.8 congelado
(`portao_qualidade.py`) × caminho atual, mesmo Tesseract/idioma/config:

| critério | exigência | antes | depois | veredito |
| --- | --- | ---: | ---: | --- |
| caracteres reconhecidos | ≥ 99,9% | 32.705 | 32.705 (100,00%) | OK |
| confiança média | ≥ antes − 0,5 | 88,64 | 88,64 | OK |
| diff palavra a palavra | sem perda | — | 0 páginas divergentes | OK |

O texto de OCR do caminho novo é **idêntico** ao antigo — todo o ganho de
tempo vem de paralelismo e de não fazer trabalho inútil, nunca de degradar o
reconhecimento.

## Verificações que acompanharam a medição

- `tests/regressao/verificar_regressao.py`: **nenhuma regressão**, 54 melhoras
  de preservação de miolo (Tarefa A).
- Suíte `pytest tests`: 42 passed, 1 skipped.

## Pesos da barra de progresso (Tarefa B) calibrados por estas medições

`P_LIMPEZA = 1.0` · `P_OCR = 2.6` · `P_NUMERA = 0.2` · `P_EXPORT = 0.4` ·
`P_DIVIDE = 0.2` — proporcionais aos s/página medidos acima, para a barra ser
aproximadamente linear no tempo real.

## Hotspots (cProfile) — depois

### embutir_ocr

O `image_to_data` sumiu do perfil do processo pai (o Tesseract agora roda nos
workers); o custo residual no pai é o parse de elementos:

| função | tempo cumulativo (s) | tempo próprio (s) | chamadas |
| --- | ---: | ---: | ---: |
| `_elementos` (limpa_pdf_mpsc.py) | 18,1 | 0,0 | 81 |
| `_iter_elementos` (limpa_pdf_mpsc.py) | 18,1 | 14,6 | 81 |
| `parse_content_stream` (pikepdf) | 3,3 | 3,3 | 162 |

### exportar_md

| função | tempo cumulativo (s) | tempo próprio (s) | chamadas |
| --- | ---: | ---: | ---: |
| `_tabelas_md` (limpa_pdf_mpsc.py) | 87,8 | 0,0 | 1 |
| `find_tables` (pdfplumber) | 68,7 | 0,0 | **31** (era 81) |
| `_elementos` (limpa_pdf_mpsc.py) | 17,7 | 0,0 | 81 |

> Próximo alvo natural, se um dia for preciso mais: `_iter_elementos` aparece
> ~18 s em cada etapa (o content stream é reparseado por etapa). Fora do
> escopo da Tarefa C — o ganho de 2× foi atingido sem tocar em qualidade.
