# RELATORIO_EPROC — diagnóstico de `ex1.pdf` (e-proc/TJSC)

- Original: `ex1.pdf` — 34 página(s)
- Limpo:    `ex1 limpo.pdf` — 34 página(s)
- Critério atual de aproveitável: `_texto_e_aproveitavel` (>= 20 chars, frac_alnum >= 0.45, frac_lixo <= 0.20)
- Imagem de página inteira: >= 80% da largura E altura (ou tiras emendadas)

## 1. Página a página — `ex1.pdf` (original do e-proc)

Img inteira 'via form' = o scan está DENTRO de um Form XObject (Do de /TPLn), invisível para `_elementos` hoje.

| Pág | Chars | Alnum | Lixo | Tinta | Dens (ch/1k px) | Imgs | Img inteira? | Aproveitável? | Camada deficiente? | Classe proposta | Estratégia |
|---:|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|---|---|
| 1 | 293 | 0.92 | 0.00 | 0.011 | 54.6 | 0 | nao | sim | nao | NATIVA_DIGITAL | extrai texto, sem OCR |
| 2 | 264 | 0.89 | 0.00 | 0.024 | 21.8 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 3 | 264 | 0.89 | 0.00 | 0.029 | 17.9 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 4 | 264 | 0.89 | 0.00 | 0.024 | 21.6 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 5 | 264 | 0.89 | 0.00 | 0.023 | 22.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 6 | 264 | 0.89 | 0.00 | 0.013 | 40.6 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 7 | 264 | 0.89 | 0.00 | 0.026 | 20.5 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 8 | 264 | 0.89 | 0.00 | 0.073 | 7.2 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 9 | 264 | 0.89 | 0.00 | 0.078 | 6.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 10 | 264 | 0.89 | 0.00 | 0.023 | 22.4 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 11 | 265 | 0.89 | 0.00 | 0.054 | 9.8 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 12 | 265 | 0.89 | 0.00 | 0.045 | 11.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 13 | 265 | 0.89 | 0.00 | 0.022 | 23.5 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 14 | 265 | 0.89 | 0.00 | 0.021 | 24.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 15 | 265 | 0.89 | 0.00 | 0.021 | 25.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 16 | 265 | 0.89 | 0.00 | 0.042 | 12.5 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 17 | 265 | 0.89 | 0.00 | 0.023 | 23.2 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 18 | 265 | 0.89 | 0.00 | 0.030 | 17.8 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 19 | 265 | 0.89 | 0.00 | 0.034 | 15.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 20 | 265 | 0.89 | 0.00 | 0.034 | 15.4 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 21 | 265 | 0.89 | 0.00 | 0.032 | 16.4 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 22 | 265 | 0.89 | 0.00 | 0.040 | 13.1 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 23 | 265 | 0.89 | 0.00 | 0.008 | 63.8 | 1 | sim (via form) | sim | nao | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 24 | 265 | 0.89 | 0.00 | 0.018 | 29.0 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 25 | 265 | 0.89 | 0.00 | 0.025 | 21.2 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 26 | 265 | 0.89 | 0.00 | 0.014 | 38.7 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 27 | 265 | 0.89 | 0.00 | 0.043 | 12.2 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 28 | 265 | 0.89 | 0.00 | 0.066 | 8.0 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 29 | 265 | 0.89 | 0.00 | 0.043 | 12.4 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 30 | 265 | 0.89 | 0.00 | 0.034 | 15.6 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 31 | 982 | 0.89 | 0.00 | 0.030 | 65.5 | 0 | nao | sim | nao | NATIVA_DIGITAL | extrai texto, sem OCR |
| 32 | 270 | 0.91 | 0.00 | 0.010 | 54.9 | 0 | nao | sim | nao | NATIVA_DIGITAL | extrai texto, sem OCR |
| 33 | 61 | 0.85 | 0.00 | 0.075 | 1.6 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |
| 34 | 61 | 0.85 | 0.00 | 0.095 | 1.3 | 1 | sim (via form) | sim | SIM | HIBRIDA_COM_OCR | reusa camada existente (padrao) |

## 2. Página a página — `ex1 limpo.pdf` (saída atual)

| Pág | Chars | Alnum | Lixo | Tinta | Img inteira? | Aproveitável? |
|---:|---:|---:|---:|---:|:--:|:--:|
| 1 | 16 | 0.85 | 0.00 | 0.000 | nao | NAO |
| 2 | 212 | 0.90 | 0.00 | 0.024 | sim | sim |
| 3 | 212 | 0.90 | 0.00 | 0.029 | sim | sim |
| 4 | 212 | 0.90 | 0.00 | 0.024 | sim | sim |
| 5 | 212 | 0.90 | 0.00 | 0.023 | sim | sim |
| 6 | 212 | 0.90 | 0.00 | 0.013 | sim | sim |
| 7 | 212 | 0.90 | 0.00 | 0.026 | sim | sim |
| 8 | 212 | 0.90 | 0.00 | 0.073 | sim | sim |
| 9 | 212 | 0.90 | 0.00 | 0.078 | sim | sim |
| 10 | 213 | 0.90 | 0.00 | 0.023 | sim | sim |
| 11 | 213 | 0.90 | 0.00 | 0.054 | sim | sim |
| 12 | 213 | 0.90 | 0.00 | 0.045 | sim | sim |
| 13 | 213 | 0.90 | 0.00 | 0.022 | sim | sim |
| 14 | 213 | 0.90 | 0.00 | 0.021 | sim | sim |
| 15 | 213 | 0.90 | 0.00 | 0.020 | sim | sim |
| 16 | 213 | 0.90 | 0.00 | 0.042 | sim | sim |
| 17 | 213 | 0.90 | 0.00 | 0.023 | sim | sim |
| 18 | 213 | 0.90 | 0.00 | 0.030 | sim | sim |
| 19 | 213 | 0.90 | 0.00 | 0.034 | sim | sim |
| 20 | 213 | 0.90 | 0.00 | 0.034 | sim | sim |
| 21 | 213 | 0.90 | 0.00 | 0.032 | sim | sim |
| 22 | 213 | 0.90 | 0.00 | 0.040 | sim | sim |
| 23 | 213 | 0.90 | 0.00 | 0.008 | sim | sim |
| 24 | 213 | 0.90 | 0.00 | 0.018 | sim | sim |
| 25 | 213 | 0.90 | 0.00 | 0.025 | sim | sim |
| 26 | 213 | 0.90 | 0.00 | 0.014 | sim | sim |
| 27 | 213 | 0.90 | 0.00 | 0.043 | sim | sim |
| 28 | 213 | 0.90 | 0.00 | 0.066 | sim | sim |
| 29 | 213 | 0.90 | 0.00 | 0.042 | sim | sim |
| 30 | 213 | 0.90 | 0.00 | 0.034 | sim | sim |
| 31 | 930 | 0.89 | 0.00 | 0.030 | nao | sim |
| 32 | 17 | 0.86 | 0.00 | 0.000 | nao | NAO |
| 33 | 20 | 0.87 | 0.00 | 0.075 | sim | sim |
| 34 | 20 | 0.80 | 0.00 | 0.095 | sim | sim |

## 3. Comparação original × limpo (o limpo preservou a camada do e-proc?)

| Pág | Chars orig | Chars limpo | Razão | Palavras da camada presentes no limpo | Observação |
|---:|---:|---:|---:|---:|---|
| 1 | 293 | 16 | 0.05 | 0.00 | LIMPO PRATICAMENTE SEM TEXTO |
| 2 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 3 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 4 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 5 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 6 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 7 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 8 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 9 | 264 | 212 | 0.80 | 0.82 | camada e-proc preservada |
| 10 | 264 | 213 | 0.81 | 0.82 | camada e-proc preservada |
| 11 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 12 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 13 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 14 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 15 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 16 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 17 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 18 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 19 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 20 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 21 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 22 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 23 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 24 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 25 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 26 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 27 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 28 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 29 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 30 | 265 | 213 | 0.80 | 0.82 | camada e-proc preservada |
| 31 | 982 | 930 | 0.95 | 0.97 | camada e-proc preservada |
| 32 | 270 | 17 | 0.06 | 0.00 | LIMPO PRATICAMENTE SEM TEXTO |
| 33 | 61 | 20 | 0.33 | 0.00 | limpo perdeu >50% dos chars |
| 34 | 61 | 20 | 0.33 | 0.00 | limpo perdeu >50% dos chars |

## 4. Resumo por classe proposta

- **HIBRIDA_COM_OCR**: 31 página(s) — 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33...
- **NATIVA_DIGITAL**: 3 página(s) — 1, 31, 32

## 5. Candidatas a camada DEFICIENTE (calibragem de `FRAC_TEXTO_MIN_HIBRIDO`)

Páginas híbridas ordenadas por densidade (chars por 1000 px de tinta) — as de densidade mais baixa têm muita tinta e pouco texto reconhecido:

| Pág | Chars | Tinta | Dens (ch/1k px) |
|---:|---:|---:|---:|
| 34 | 61 | 0.095 | 1.3 |
| 33 | 61 | 0.075 | 1.6 |
| 9 | 264 | 0.078 | 6.7 |
| 8 | 264 | 0.073 | 7.2 |
| 28 | 265 | 0.066 | 8.0 |
| 11 | 265 | 0.054 | 9.8 |
| 12 | 265 | 0.045 | 11.7 |
| 27 | 265 | 0.043 | 12.2 |
| 29 | 265 | 0.043 | 12.4 |
| 16 | 265 | 0.042 | 12.5 |
| 22 | 265 | 0.040 | 13.1 |
| 20 | 265 | 0.034 | 15.4 |
| 30 | 265 | 0.034 | 15.6 |
| 19 | 265 | 0.034 | 15.7 |
| 21 | 265 | 0.032 | 16.4 |
| 18 | 265 | 0.030 | 17.8 |
| 3 | 264 | 0.029 | 17.9 |
| 7 | 264 | 0.026 | 20.5 |
| 25 | 265 | 0.025 | 21.2 |
| 4 | 264 | 0.024 | 21.6 |
| 2 | 264 | 0.024 | 21.8 |
| 10 | 264 | 0.023 | 22.4 |
| 5 | 264 | 0.023 | 22.7 |
| 17 | 265 | 0.023 | 23.2 |
| 13 | 265 | 0.022 | 23.5 |
| 14 | 265 | 0.021 | 24.7 |
| 15 | 265 | 0.021 | 25.7 |
| 24 | 265 | 0.018 | 29.0 |
| 26 | 265 | 0.014 | 38.7 |
| 6 | 264 | 0.013 | 40.6 |
| 23 | 265 | 0.008 | 63.8 |

## 6. Conclusões do diagnóstico (estrutura confirmada por inspeção)

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
   em forms, e o ramo de imagem via `Do` compara Subtype com `"\Image"`
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
   `C:\Users\User\Desktop\PDFs para Teste\exemplos\`. Para rodar a
   bateria de `tests/regressao/verificar_regressao.py` é preciso
   recolocá-los em `exemplos/`.


## 7. Portão de qualidade (portao_eproc.py — `nunca` × `auto` sobre o arquivo LIMPO)

| Pág | Chars nunca | Chars auto | Palavras nunca | Palavras auto | Moldura no auto? | Conf média OCR |
|---:|---:|---:|---:|---:|:--:|---:|
| 2 | 170 | 933 | 18 | 84 | — | 87 |
| 8 | 170 | 3608 | 18 | 277 | — | 92 |
| 9 | 170 | 937 | 18 | 73 | — | 80 |
| 23 | 170 | 446 | 18 | 30 | — | 73 |
| 33 | 1 | 1 | 0 | 0 | — | — |

Critérios: (1) chars(auto) >= chars(nunca) em toda a amostra — o auto é ADITIVO, nada é removido; (2) moldura presente onde existia; (3) confiança média >= 40. **Resultado: APROVADO**.

Nota: após a LIMPEZA a pág. 23 cai a densidade 43,1 (< 45) e também recebe OCR aditivo no auto — direção segura (só acrescenta; dedup e corte de confiança protegem).
