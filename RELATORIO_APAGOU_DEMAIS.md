# Relatório de auditoria — "apagou demais"

> **Sumário executivo (diagnóstico → correção, v2.9).**
>
> **O que se perdia:** o `Apagou demais ORIGINAL.pdf` é escaneado — a única
> camada de texto é o carimbo "fls. NNN"; a certidão e as tabelas vivem em
> IMAGENS. Com a v2.8, **56 de 81 páginas perdiam >30% da tinta renderizada**
> (págs. 65–66: **100%** — o print de sistema com as tabelas de
> empenhos/licitações/contratos virava página em branco).
>
> **Causa-raiz (medida, não hipótese):** os cortes de cabeçalho/rodapé
> removiam qualquer imagem/caminho que TOCASSE o corte
> (`bbox[3] >= cut_topo - 2`). As imagens do corpo terminam em y=753,
> encostadas na régua (y=754) → eram engolidas inteiras. Agravante: a borda
> superior dos prints, colados na mesma posição em dezenas de páginas,
> virava "régua" por repetição e propagava o corte (H1 do prompt).
> As hipóteses H2 (dígitos→`#` no boilerplate), H3 (laço de extensão),
> H4 (`boiler_base_P`) e H5 (assinatura vetorial) **não se confirmaram**
> neste acervo — as regras correspondentes não foram alteradas.
> O mesmo mecanismo cortava conteúdo nos exemplos 3, 4 e 5 (mensagens de
> WhatsApp no topo, título de recibo, texto do rodapé).
>
> **Correções aplicadas:** (1) regra do CENTRO nos cortes (só remove
> elemento majoritariamente dentro da faixa; exceção: tarja da assinatura);
> (2) zonas de tabela protegidas (`zonas_tabela`, filtro 2×2);
> (3) limiares de régua medidos no acervo (`LIM_REGUA_TOPO=0.85`,
> `LIM_REGUA_BASE=0.11`) e rejeição de borda de caixa (`_regua_caixa`);
> (4) rollback por página (`LIMITE_PERDA_PAGINA=35%` dos chars,
> `LIMITE_PERDA_AREA_IMG=10%` da área).
>
> **Resultado:** regressão automatizada (tests/regressao) sem falhas, com
> 54 melhoras de preservação; renders das págs. 13/65/66 confirmam certidão
> e tabelas íntegras com cabeçalho, rodapé, fls, carimbo e assinatura
> removidos. As tabelas abaixo refletem o comportamento **pós-correção**:
> cada página perde apenas os 7 chars do "fls. NNN" e 1,4% de área (o logo).

**Arquivo:** `Apagou demais ORIGINAL.pdf` · **Páginas:** 81

A limpeza foi executada SEM salvar; para cada página e cada motivo de remoção, a página foi reconstruída sem os elementos daquele motivo e o texto foi reextraído (pypdfium2). Os números abaixo são perda REAL de caracteres (não brancos), medida — não estimada.

## 1. Ranking global — perda por motivo

(área = soma, em páginas inteiras equivalentes, das imagens removidas — em documento escaneado o conteúdo está nas imagens)

| motivo | chars removidos | % do texto do documento | área de imagens removida (págs equiv.) | páginas atingidas |
| --- | ---: | ---: | ---: | --- |
| `boiler_imagem` | 0 | 0.00% | 1.07 | 1, 2, 3, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26 ... |
| `corte_topo` | 364 | 64.20% | 0.00 | 10, 16, 17, 18, 19, 20, 26, 27, 28, 29, 30, 36, 37, 38, 39, 40, 46, 47, 48, 49 ... |
| `boiler_texto` | 175 | 30.86% | 0.00 | 1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 31, 32, 33, 34, 35 ... |
| `faixa_fixa_topo_txt` | 28 | 4.94% | 0.00 | 6, 7, 8, 9 |
| `cluster_topo` | 0 | 0.00% | 0.00 |  |
| `glifo_orfao` | 0 | 0.00% | 0.00 |  |
| `boiler_path` | 0 | 0.00% | 0.00 |  |
| `corte_base` | 0 | 0.00% | 0.00 |  |
| `carimbo_copia` | 0 | 0.00% | 0.00 |  |
| `faixa_base_vetorial` | 0 | 0.00% | 0.00 |  |

## 2. Perda por página e por motivo

(só páginas com remoção; % relativa ao texto/área da página)

| pág | chars da pág | motivo | chars removidos | % da pág | área de imagens removida |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 1 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 2 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 2 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 3 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 3 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 4 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 5 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 6 | 7 | `faixa_fixa_topo_txt` | 7 | 100.0% | 0.0% |
| 7 | 7 | `faixa_fixa_topo_txt` | 7 | 100.0% | 0.0% |
| 8 | 7 | `faixa_fixa_topo_txt` | 7 | 100.0% | 0.0% |
| 9 | 7 | `faixa_fixa_topo_txt` | 7 | 100.0% | 0.0% |
| 10 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 10 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 11 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 11 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 12 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 12 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 13 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 13 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 14 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 14 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 15 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 15 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 16 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 16 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 17 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 17 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 18 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 18 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 19 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 19 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 20 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 20 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 21 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 21 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 22 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 22 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 23 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 23 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 24 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 24 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 25 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 25 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 26 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 26 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 27 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 27 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 28 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 28 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 29 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 29 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 30 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 30 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 31 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 31 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 32 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 32 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 33 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 33 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 34 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 34 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 35 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 35 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 36 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 36 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 37 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 37 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 38 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 38 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 39 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 39 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 40 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 40 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 41 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 41 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 42 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 42 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 43 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 43 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 44 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 44 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 45 | 7 | `boiler_texto` | 7 | 100.0% | 0.0% |
| 45 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 46 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 46 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 47 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 47 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 48 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 48 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 49 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 49 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 50 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 50 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 51 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 51 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 52 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 52 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 53 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 53 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 54 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 54 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 55 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 55 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 56 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 56 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 57 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 57 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 58 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 58 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 59 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 59 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 60 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 60 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 61 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 61 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 62 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 62 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 63 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 63 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 64 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 64 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 65 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 65 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 66 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 66 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 67 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 67 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 68 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 68 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 69 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 69 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 70 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 70 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 71 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 71 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 72 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 72 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 73 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 73 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 74 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 74 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 75 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 75 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 76 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 76 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 77 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 77 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 78 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 78 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 79 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 79 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 80 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 80 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |
| 81 | 7 | `corte_topo` | 7 | 100.0% | 0.0% |
| 81 | 7 | `boiler_imagem` | 0 | 0.0% | 1.4% |

## 3. Texto efetivamente removido, por motivo

### Motivo `corte_topo` — 52 linha(s) removida(s)

- (pág 10) `fls. 109`
- (pág 16) `fls. 115`
- (pág 17) `fls. 116`
- (pág 18) `fls. 117`
- (pág 19) `fls. 118`
- (pág 20) `fls. 119`
- (pág 26) `fls. 125`
- (pág 27) `fls. 126`
- (pág 28) `fls. 127`
- (pág 29) `fls. 128`
- (pág 30) `fls. 129`
- (pág 36) `fls. 135`
- (pág 37) `fls. 136`
- (pág 38) `fls. 137`
- (pág 39) `fls. 138`
- (pág 40) `fls. 139`
- (pág 46) `fls. 145`
- (pág 47) `fls. 146`
- (pág 48) `fls. 147`
- (pág 49) `fls. 148`
- (pág 50) `fls. 149`
- (pág 51) `fls. 150`
- (pág 52) `fls. 151`
- (pág 53) `fls. 152`
- (pág 54) `fls. 153`
- (pág 55) `fls. 154`
- (pág 56) `fls. 155`
- (pág 57) `fls. 156`
- (pág 58) `fls. 157`
- (pág 59) `fls. 158`
- (pág 60) `fls. 159`
- (pág 61) `fls. 160`
- (pág 62) `fls. 161`
- (pág 63) `fls. 162`
- (pág 64) `fls. 163`
- (pág 65) `fls. 164`
- (pág 66) `fls. 165`
- (pág 67) `fls. 166`
- (pág 68) `fls. 167`
- (pág 69) `fls. 168`
- (pág 70) `fls. 169`
- (pág 71) `fls. 170`
- (pág 72) `fls. 171`
- (pág 73) `fls. 172`
- (pág 74) `fls. 173`
- (pág 75) `fls. 174`
- (pág 76) `fls. 175`
- (pág 77) `fls. 176`
- (pág 78) `fls. 177`
- (pág 79) `fls. 178`
- (pág 80) `fls. 179`
- (pág 81) `fls. 180`

### Motivo `boiler_texto` — 25 linha(s) removida(s)

- (pág 1) `fls. 100`
- (pág 2) `fls. 101`
- (pág 3) `fls. 102`
- (pág 4) `fls. 103`
- (pág 5) `fls. 104`
- (pág 11) `fls. 110`
- (pág 12) `fls. 111`
- (pág 13) `fls. 112`
- (pág 14) `fls. 113`
- (pág 15) `fls. 114`
- (pág 21) `fls. 120`
- (pág 22) `fls. 121`
- (pág 23) `fls. 122`
- (pág 24) `fls. 123`
- (pág 25) `fls. 124`
- (pág 31) `fls. 130`
- (pág 32) `fls. 131`
- (pág 33) `fls. 132`
- (pág 34) `fls. 133`
- (pág 35) `fls. 134`
- (pág 41) `fls. 140`
- (pág 42) `fls. 141`
- (pág 43) `fls. 142`
- (pág 44) `fls. 143`
- (pág 45) `fls. 144`

### Motivo `faixa_fixa_topo_txt` — 4 linha(s) removida(s)

- (pág 6) `fls. 105`
- (pág 7) `fls. 106`
- (pág 8) `fls. 107`
- (pág 9) `fls. 108`

## 4. Diff de texto extraído — `Apagou demais ORIGINAL.pdf` × `Apagou demais LIMPO.pdf`

81 linha(s) do ORIGINAL não aparecem no LIMPO:

### Página 1 — 1 linha(s) perdida(s)

- `fls. 100`

### Página 2 — 1 linha(s) perdida(s)

- `fls. 101`

### Página 3 — 1 linha(s) perdida(s)

- `fls. 102`

### Página 4 — 1 linha(s) perdida(s)

- `fls. 103`

### Página 5 — 1 linha(s) perdida(s)

- `fls. 104`

### Página 6 — 1 linha(s) perdida(s)

- `fls. 105`

### Página 7 — 1 linha(s) perdida(s)

- `fls. 106`

### Página 8 — 1 linha(s) perdida(s)

- `fls. 107`

### Página 9 — 1 linha(s) perdida(s)

- `fls. 108`

### Página 10 — 1 linha(s) perdida(s)

- `fls. 109`

### Página 11 — 1 linha(s) perdida(s)

- `fls. 110`

### Página 12 — 1 linha(s) perdida(s)

- `fls. 111`

### Página 13 — 1 linha(s) perdida(s)

- `fls. 112`

### Página 14 — 1 linha(s) perdida(s)

- `fls. 113`

### Página 15 — 1 linha(s) perdida(s)

- `fls. 114`

### Página 16 — 1 linha(s) perdida(s)

- `fls. 115`

### Página 17 — 1 linha(s) perdida(s)

- `fls. 116`

### Página 18 — 1 linha(s) perdida(s)

- `fls. 117`

### Página 19 — 1 linha(s) perdida(s)

- `fls. 118`

### Página 20 — 1 linha(s) perdida(s)

- `fls. 119`

### Página 21 — 1 linha(s) perdida(s)

- `fls. 120`

### Página 22 — 1 linha(s) perdida(s)

- `fls. 121`

### Página 23 — 1 linha(s) perdida(s)

- `fls. 122`

### Página 24 — 1 linha(s) perdida(s)

- `fls. 123`

### Página 25 — 1 linha(s) perdida(s)

- `fls. 124`

### Página 26 — 1 linha(s) perdida(s)

- `fls. 125`

### Página 27 — 1 linha(s) perdida(s)

- `fls. 126`

### Página 28 — 1 linha(s) perdida(s)

- `fls. 127`

### Página 29 — 1 linha(s) perdida(s)

- `fls. 128`

### Página 30 — 1 linha(s) perdida(s)

- `fls. 129`

### Página 31 — 1 linha(s) perdida(s)

- `fls. 130`

### Página 32 — 1 linha(s) perdida(s)

- `fls. 131`

### Página 33 — 1 linha(s) perdida(s)

- `fls. 132`

### Página 34 — 1 linha(s) perdida(s)

- `fls. 133`

### Página 35 — 1 linha(s) perdida(s)

- `fls. 134`

### Página 36 — 1 linha(s) perdida(s)

- `fls. 135`

### Página 37 — 1 linha(s) perdida(s)

- `fls. 136`

### Página 38 — 1 linha(s) perdida(s)

- `fls. 137`

### Página 39 — 1 linha(s) perdida(s)

- `fls. 138`

### Página 40 — 1 linha(s) perdida(s)

- `fls. 139`

### Página 41 — 1 linha(s) perdida(s)

- `fls. 140`

### Página 42 — 1 linha(s) perdida(s)

- `fls. 141`

### Página 43 — 1 linha(s) perdida(s)

- `fls. 142`

### Página 44 — 1 linha(s) perdida(s)

- `fls. 143`

### Página 45 — 1 linha(s) perdida(s)

- `fls. 144`

### Página 46 — 1 linha(s) perdida(s)

- `fls. 145`

### Página 47 — 1 linha(s) perdida(s)

- `fls. 146`

### Página 48 — 1 linha(s) perdida(s)

- `fls. 147`

### Página 49 — 1 linha(s) perdida(s)

- `fls. 148`

### Página 50 — 1 linha(s) perdida(s)

- `fls. 149`

### Página 51 — 1 linha(s) perdida(s)

- `fls. 150`

### Página 52 — 1 linha(s) perdida(s)

- `fls. 151`

### Página 53 — 1 linha(s) perdida(s)

- `fls. 152`

### Página 54 — 1 linha(s) perdida(s)

- `fls. 153`

### Página 55 — 1 linha(s) perdida(s)

- `fls. 154`

### Página 56 — 1 linha(s) perdida(s)

- `fls. 155`

### Página 57 — 1 linha(s) perdida(s)

- `fls. 156`

### Página 58 — 1 linha(s) perdida(s)

- `fls. 157`

### Página 59 — 1 linha(s) perdida(s)

- `fls. 158`

### Página 60 — 1 linha(s) perdida(s)

- `fls. 159`

### Página 61 — 1 linha(s) perdida(s)

- `fls. 160`

### Página 62 — 1 linha(s) perdida(s)

- `fls. 161`

### Página 63 — 1 linha(s) perdida(s)

- `fls. 162`

### Página 64 — 1 linha(s) perdida(s)

- `fls. 163`

### Página 65 — 1 linha(s) perdida(s)

- `fls. 164`

### Página 66 — 1 linha(s) perdida(s)

- `fls. 165`

### Página 67 — 1 linha(s) perdida(s)

- `fls. 166`

### Página 68 — 1 linha(s) perdida(s)

- `fls. 167`

### Página 69 — 1 linha(s) perdida(s)

- `fls. 168`

### Página 70 — 1 linha(s) perdida(s)

- `fls. 169`

### Página 71 — 1 linha(s) perdida(s)

- `fls. 170`

### Página 72 — 1 linha(s) perdida(s)

- `fls. 171`

### Página 73 — 1 linha(s) perdida(s)

- `fls. 172`

### Página 74 — 1 linha(s) perdida(s)

- `fls. 173`

### Página 75 — 1 linha(s) perdida(s)

- `fls. 174`

### Página 76 — 1 linha(s) perdida(s)

- `fls. 175`

### Página 77 — 1 linha(s) perdida(s)

- `fls. 176`

### Página 78 — 1 linha(s) perdida(s)

- `fls. 177`

### Página 79 — 1 linha(s) perdida(s)

- `fls. 178`

### Página 80 — 1 linha(s) perdida(s)

- `fls. 179`

### Página 81 — 1 linha(s) perdida(s)

- `fls. 180`

## 5. Dados auxiliares (verificação das hipóteses)

### Cortes de régua por página (analisar → cortes)

| pág | cut_topo (pt) | cut_topo/H | cut_base (pt) | cut_base/H |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 764.4 | 0.908 | 57.8 | 0.069 |
| 2 | 764.4 | 0.908 | 57.8 | 0.069 |
| 3 | 764.4 | 0.908 | 57.8 | 0.069 |
| 10 | 764.4 | 0.908 | 57.8 | 0.069 |
| 11 | 764.4 | 0.908 | 57.8 | 0.069 |
| 12 | 764.4 | 0.908 | 57.8 | 0.069 |
| 13 | 764.4 | 0.908 | 57.8 | 0.069 |
| 14 | 764.4 | 0.908 | 57.8 | 0.069 |
| 15 | 764.4 | 0.908 | 57.8 | 0.069 |
| 16 | 764.4 | 0.908 | — | — |
| 17 | 764.4 | 0.908 | 57.8 | 0.069 |
| 18 | 764.4 | 0.908 | 57.8 | 0.069 |
| 19 | 764.4 | 0.908 | 57.8 | 0.069 |
| 20 | 764.4 | 0.908 | 57.8 | 0.069 |
| 21 | 764.4 | 0.908 | 57.8 | 0.069 |
| 22 | 764.4 | 0.908 | 57.8 | 0.069 |
| 23 | 764.4 | 0.908 | 57.8 | 0.069 |
| 24 | 764.4 | 0.908 | 57.8 | 0.069 |
| 25 | 764.4 | 0.908 | 57.8 | 0.069 |
| 26 | 764.4 | 0.908 | 57.8 | 0.069 |
| 27 | 764.4 | 0.908 | 57.8 | 0.069 |
| 28 | 764.4 | 0.908 | 57.8 | 0.069 |
| 29 | 764.4 | 0.908 | 57.8 | 0.069 |
| 30 | 764.4 | 0.908 | 57.8 | 0.069 |
| 31 | 764.4 | 0.908 | 57.8 | 0.069 |
| 32 | 764.4 | 0.908 | 57.8 | 0.069 |
| 33 | 764.4 | 0.908 | 57.8 | 0.069 |
| 34 | 764.4 | 0.908 | 57.8 | 0.069 |
| 35 | 764.4 | 0.908 | 57.8 | 0.069 |
| 36 | 764.4 | 0.908 | 57.8 | 0.069 |
| 37 | 764.4 | 0.908 | 57.8 | 0.069 |
| 38 | 764.4 | 0.908 | 57.8 | 0.069 |
| 39 | 764.4 | 0.908 | 57.8 | 0.069 |
| 40 | 764.4 | 0.908 | 57.8 | 0.069 |
| 41 | 764.4 | 0.908 | 57.8 | 0.069 |
| 42 | 764.4 | 0.908 | 57.8 | 0.069 |
| 43 | 764.4 | 0.908 | 57.8 | 0.069 |
| 44 | 764.4 | 0.908 | 57.8 | 0.069 |
| 45 | 764.4 | 0.908 | 57.8 | 0.069 |
| 46 | 764.4 | 0.908 | 57.8 | 0.069 |
| 47 | 764.4 | 0.908 | — | — |
| 48 | 764.4 | 0.908 | 57.8 | 0.069 |
| 49 | 764.4 | 0.908 | 57.8 | 0.069 |
| 50 | 764.4 | 0.908 | 57.8 | 0.069 |
| 51 | 764.4 | 0.908 | — | — |
| 52 | 764.4 | 0.908 | — | — |
| 53 | 764.4 | 0.908 | 57.8 | 0.069 |
| 54 | 764.4 | 0.908 | 57.8 | 0.069 |
| 55 | 764.4 | 0.908 | 57.8 | 0.069 |
| 56 | 764.4 | 0.908 | 57.8 | 0.069 |
| 57 | 764.4 | 0.908 | 57.8 | 0.069 |
| 58 | 764.4 | 0.908 | 57.8 | 0.069 |
| 59 | 764.4 | 0.908 | 57.8 | 0.069 |
| 60 | 764.4 | 0.908 | 57.8 | 0.069 |
| 61 | 764.4 | 0.908 | — | — |
| 62 | 764.4 | 0.908 | 57.8 | 0.069 |
| 63 | 764.4 | 0.908 | 57.8 | 0.069 |
| 64 | 764.4 | 0.908 | 57.8 | 0.069 |
| 65 | 764.4 | 0.908 | — | — |
| 66 | 764.4 | 0.908 | — | — |
| 67 | 764.4 | 0.908 | 57.8 | 0.069 |
| 68 | 764.4 | 0.908 | 57.8 | 0.069 |
| 69 | 764.4 | 0.908 | 57.8 | 0.069 |
| 70 | 764.4 | 0.908 | 57.8 | 0.069 |
| 71 | 764.4 | 0.908 | 57.8 | 0.069 |
| 72 | 764.4 | 0.908 | 57.8 | 0.069 |
| 73 | 764.4 | 0.908 | 57.8 | 0.069 |
| 74 | 764.4 | 0.908 | 57.8 | 0.069 |
| 75 | 764.4 | 0.908 | 57.8 | 0.069 |
| 76 | 764.4 | 0.908 | 57.8 | 0.069 |
| 77 | 764.4 | 0.908 | 57.8 | 0.069 |
| 78 | 764.4 | 0.908 | 57.8 | 0.069 |
| 79 | 764.4 | 0.908 | — | — |
| 80 | 764.4 | 0.908 | — | — |
| 81 | 764.4 | 0.908 | 57.8 | 0.069 |

### Chaves de boilerplate de TEXTO (forma normalizada, dígito→#)

3 chave(s) no total; 0 com texto só de `#`/pontuação (suspeita H2):

- `('I', 29, 94, 'T')`
- `('PL', 190, 70, 134, 40, 1615)`
- `('T', 202, 'iov')`

