# Protocolo de teste — Limpa PDF × IAs de chat (Gemini, ChatGPT, Claude)

Objetivo: **medir com evidências** (não com impressões) quanto o Limpa PDF
melhora o uso de um procedimento por uma IA, comparando o MESMO documento em
4 formas. Cada resposta da IA precisa vir com citação literal + página, e o
gabarito é preenchido por você ANTES — o que torna qualquer resultado
verificável e elimina resultado inventado.

> ⚠️ **SIGILO PRIMEIRO.** Enviar um procedimento real para ChatGPT/Gemini/
> Claude públicos transfere o conteúdo para servidores de terceiros — o
> oposto do princípio do Limpa PDF (100% local). Para este teste use
> APENAS: documento de teste sem sigilo, peça pública, ou um arquivo
> anonimizado. No MPSC, o teste "oficial" deve ser no **Copilot 365
> institucional**.

---

## 1. Preparar os 4 arquivos (condições do teste)

Com o mesmo PDF de origem (ideal: um com páginas escaneadas ou prints, como
um TC de delegacia — é onde o OCR aparece):

| Cond. | Arquivo | Como gerar |
|---|---|---|
| **A** | Original | o PDF bruto, sem tocar |
| **B** | Limpo SEM OCR | `python limpa_pdf_mpsc.py "arquivo.pdf" --sem-cabecalho --max-mb 0` |
| **C** | Limpo COM OCR | `python limpa_pdf_mpsc.py "arquivo.pdf" --sem-cabecalho --ocr --max-mb 0` |
| **D** | Markdown | o `.md` gerado junto com C (acrescente `--md`) |

Anote desde já (planilha da seção 4): **tamanho em MB de cada arquivo** e o
**nº de caracteres do D** (no PowerShell:
`(Get-Content arquivo.md -Raw).Length`). Caracteres ÷ 4 ≈ tokens — é o
custo de janela de contexto que cada forma impõe à IA.

O que cada comparação prova (amarrado ao código-fonte):

- **A × B** — remoção da moldura (assinatura lateral, carimbo CÓPIA,
  cabeçalho/rodapé): menos ruído e menos tokens sem perder conteúdo.
- **B × C** — o valor do OCR: páginas escaneadas e prints não têm camada de
  texto em A/B; a IA que só lê texto do PDF fica CEGA para elas. O C embute
  texto invisível selecionável (400 dpi, tessdata_best).
- **C × D** — a exportação estruturada: metadados, `## Página N de TOTAL`
  contínuo, peças como títulos, tabelas Markdown reais e a ORIGEM de cada
  página (`_[OCR do LIMPAPDF]_` etc.).
- **Paginação** — A não tem números de página confiáveis; B/C/D carimbam
  `[Pagina N de TOTAL]` — a IA consegue CITAR a página de cada informação.

## 2. Montar o gabarito (ANTES de qualquer chat)

Abra o documento você mesmo e preencha **10 perguntas com resposta e página
verificadas**. Use esta distribuição — cada tipo mede um recurso do
programa:

- **Q1–Q3 · texto nativo** (fatos em páginas com texto digital): nº do
  processo, datas, nomes de peças. *Todas as condições deveriam acertar.*
- **Q4–Q6 · conteúdo escaneado/print** (fatos que SÓ existem dentro de
  imagem: um dado do BO escaneado, um trecho de print de WhatsApp): *é aqui
  que A e B tendem a falhar e C/D a acertar — a prova do OCR.*
- **Q7 · tabela** (um valor dentro de uma tabela real do documento).
- **Q8 · localização**: "Em que página está X?" — *prova da paginação.*
- **Q9–Q10 · ARMADILHAS**: perguntas cuja resposta você CONFIRMOU que não
  existe no documento (ex.: um CPF, um valor de fiança, uma testemunha que
  não constam). A resposta correta é "não consta". *Mede alucinação.*

Exemplo real (do `exemplos/ex1.pdf` deste projeto — confira no original
antes de usar): Q1: "Qual o número do processo?" → `5000082-11.2025.8.24.0006`;
Q2: "Qual o tipo do Documento 1?" → `AUTO DE PRISÃO EM FLAGRANTE` (pág. 1);
Q4: "Qual a data e hora do registro do BO na Polícia Civil?" →
`11/01/2025 18h48min` (pág. 8 — só existe dentro do scan; sem OCR, invisível).

## 3. PROMPT 1 — avaliação (cole num CHAT NOVO para cada arquivo)

Regras de ouro: **um chat novo por condição** (A, B, C, D — nunca reaproveite
o chat), mesmo prompt, mesmas perguntas, mesma ordem, nas 3 plataformas.
Anexe o arquivo e cole isto (substitua as perguntas pelas suas):

```text
Você vai responder EXCLUSIVAMENTE com base no arquivo anexado. Regras
obrigatórias:

1. NÃO use conhecimento externo nem busca na internet. Só o arquivo.
2. Para CADA resposta, forneça: (a) a resposta; (b) uma CITAÇÃO LITERAL
   curta (até 20 palavras) copiada do documento que a sustenta; (c) o
   NÚMERO DA PÁGINA onde está (se o documento tiver rótulos
   "[Pagina N de TOTAL]" ou "## Página N de TOTAL", use esse número).
3. Se a informação NÃO estiver no documento ou você não conseguir lê-la,
   responda exatamente: "NÃO CONSTA / NÃO CONSIGO LER". Isso é uma
   resposta válida e correta — NUNCA deduza, estime ou complete.
4. Antes das perguntas, preencha este diagnóstico de leitura:
   - Quantas páginas o documento tem?
   - Liste 3 trechos literais de páginas diferentes (início, meio, fim).
   - Existe alguma página que você não consegue ler (sem texto)? Quais?

Responda na tabela:
| Nº | Resposta | Citação literal | Página |

Perguntas:
Q1. ...
Q2. ...
(...)
Q10. ...
```

O diagnóstico do item 4 é importante: ele registra, com evidência, se a IA
sequer CONSEGUE ler as páginas escaneadas de cada condição (em A/B a
resposta honesta costuma ser "não consigo ler as páginas X–Y").

## 4. Corrigir e anotar (planilha de resultados)

Corrija cada chat contra o SEU gabarito e preencha uma linha por
plataforma × condição (modelo CSV — mantenha este formato, o relatório da
seção 5 depende dele):

```csv
plataforma,condicao,tamanho_mb,acertos_texto_Q1a3,acertos_imagem_Q4a6,acerto_tabela_Q7,acerto_pagina_Q8,armadilhas_corretas_Q9a10,alucinacoes,citacoes_pagina_corretas,paginas_ilegiveis_reportadas,obs
ChatGPT,A_original,3.3,,,,,,,,,
ChatGPT,B_limpo_sem_ocr,,,,,,,,,,
ChatGPT,C_limpo_com_ocr,,,,,,,,,,
ChatGPT,D_markdown,,,,,,,,,,
Gemini,A_original,...
Claude,A_original,...
```

Critérios de correção (objetivos):

- **acerto** = resposta certa E citação literal que existe de fato no
  documento. Resposta certa com citação inventada = **alucinação**.
- **armadilha correta** = respondeu "NÃO CONSTA" nas Q9–Q10. Qualquer
  resposta substantiva a uma armadilha = **alucinação** (some no campo
  `alucinacoes`).
- **citações de página corretas** = das respostas certas, quantas citaram a
  página certa (0–8).
- **páginas ilegíveis reportadas** = o que a IA declarou no diagnóstico.

## 5. PROMPT 2 — relatório final (chat novo, depois de TODOS os testes)

Cole o CSV completo preenchido e este prompt (funciona em Claude, ChatGPT e
Gemini — todos geram tabela e gráfico a partir de dados fornecidos):

```text
Você é um analista de dados. Abaixo está um CSV com os resultados REAIS de
um experimento que comparou o desempenho de IAs lendo o mesmo documento em
4 formas: A_original (PDF bruto), B_limpo_sem_ocr, C_limpo_com_ocr e
D_markdown (arquivos processados pelo programa "Limpa PDF").

REGRAS: use SOMENTE os números do CSV. Não invente, não estime e não
preencha lacunas — célula vazia permanece vazia e deve ser listada como
"dado ausente". Se algum cálculo não for possível, diga o porquê.

Produza:
1. Tabela comparativa por CONDIÇÃO (média entre plataformas): % de acerto
   em texto nativo (Q1-3), % em conteúdo de imagem (Q4-6), tabela (Q7),
   localização de página (Q8), taxa de alucinação, acerto de citação de
   página, tamanho do arquivo.
2. Tabela por PLATAFORMA × condição (os dados crus, organizados).
3. GRÁFICOS de barras comparativos (gere imagem ou código matplotlib):
   (a) acerto em conteúdo de imagem por condição — o efeito do OCR;
   (b) taxa de alucinação por condição;
   (c) acerto total por plataforma e condição.
4. Um parágrafo de conclusão ESTRITAMENTE limitado ao que os dados
   mostram, citando os números; e uma lista do que os dados NÃO permitem
   concluir (limitações: nº de documentos, nº de perguntas).

CSV:
<cole aqui>
```

## 6. Resultados esperados (hipóteses a testar — não são o resultado)

Pelo funcionamento do código, espera-se: A e B falham nas Q4–Q6 (sem camada
de texto nas páginas escaneadas — a IA deve declará-las ilegíveis); C e D
as acertam via texto do OCR; D tem as melhores citações de página
(`## Página N de TOTAL` explícito) e o menor custo em tokens por conteúdo
útil; a moldura de A pode "vazar" nas citações (assinaturas repetidas,
carimbos). **Se o experimento contradisser alguma hipótese, o resultado do
experimento é que vale** — traga os números.
```

---

*Kit gerado na v2.10.1. Perguntas de exemplo verificadas em
`exemplos/ex1.pdf` e `RELATORIO_EPROC.md`; confirme no original antes de
usar. Para lotes grandes, lembre que `--max-mb 0` evita divisão em partes
(um arquivo por condição simplifica o teste).*
