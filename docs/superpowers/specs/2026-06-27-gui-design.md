# Design: GUI PySide6 do Limpa PDF (MPSC)

**Data:** 2026-06-27
**Arquivo alvo:** `gui.py` (arquivo único, iteração sobre o esqueleto v0.1 existente)
**Status:** aprovado

---

## 1. Contexto

O `gui.py` já existe como esqueleto funcional (329 linhas, v0.1) com dois `# TODO` explícitos e algumas lacunas de UX. Este design completa o esqueleto na **Opção B**: arquivo único, bem organizado, sem módulos separados desnecessários.

Funcionalidades a adicionar/corrigir:

| Item | Situação atual |
|---|---|
| Cancelamento controlado | ausente |
| Múltiplos itens no drag-and-drop | `# TODO` linha 277 |
| Botão "Abrir pasta LIMPOS" | `# TODO` linha 309 |
| Erros fatais em modal | apenas `lbl_status` em texto pequeno |
| Log rolável por arquivo | ausente |
| Polish visual institucional | mínimo |

---

## 2. Arquitetura

Arquivo único `gui.py` dividido em quatro blocos comentados:

```
# ── 1. CONSTANTES E ESTILOS ──────────────────────────────────────────────────
# ── 2. WORKER ─────────────────────────────────────────────────────────────────
# ── 3. WIDGETS AUXILIARES ─────────────────────────────────────────────────────
# ── 4. JANELA PRINCIPAL ───────────────────────────────────────────────────────
```

### Sinais do Worker

| Sinal | Assinatura | Uso |
|---|---|---|
| `progresso` | `(int, str)` | atualiza barra + texto de status |
| `log` | `(str,)` | linha nova no painel de log |
| `terminou` | `(list[str], bool)` | arquivos gerados + flag `cancelado` |
| `erro` | `(str,)` | erro fatal → `QMessageBox.critical` |

O Worker recebe `list[Path]` (em vez de `Path` único), unificando os casos de seleção de pasta, seleção de PDFs e drag-and-drop de múltiplos itens.

---

## 3. Cancelamento

Cancelamento **cooperativo** — nunca mata a thread à força para evitar PDFs corrompidos no disco.

```python
class Worker(QThread):
    _cancelar: bool = False

    def requisitar_cancelamento(self):
        self._cancelar = True
```

**Pontos de verificação** dentro do loop de arquivos:

1. **Início de cada arquivo** — antes de qualquer escrita no disco
2. **Após `embutir_ocr`** — única etapa que pode durar minutos por arquivo

Ao sair do loop por cancelamento, o Worker emite `terminou(gerados_até_agora, cancelado=True)`. Arquivos já concluídos **não são deletados**.

**Comportamento do botão:**

- Processando: rótulo muda para **"Cancelar"** (fundo vermelho escuro), conectado a `worker.requisitar_cancelamento()`
- Após `terminou(cancelado=True)`: `"Cancelado. N arquivo(s) gerado(s) antes do cancelamento."`, botão volta a "Limpar"

---

## 4. Seleção de entrada e múltiplos itens

Widget `AreaDrop(QFrame)` centraliza toda a lógica de entrada:

```
┌─────────────────────────────────────────────────────┐
│  [Selecionar pasta]   [Selecionar PDF(s)]           │
│                                                     │
│  Arraste pastas ou PDFs aqui                        │
└─────────────────────────────────────────────────────┘
```

- **"Selecionar PDF(s)"** usa `QFileDialog.getOpenFileNames` (múltipla seleção)
- **"Selecionar pasta"** usa `getExistingDirectory` — expande recursivamente no Worker
- **Drag-and-drop:** `dropEvent` coleta todas as URLs, separa pastas de PDFs, monta `list[Path]` unificada

**Label de seleção:**

- 1 item: `"Pasta selecionada: C:\...\Processo123"` ou `"1 PDF selecionado: nome.pdf"`
- N > 1: `"5 PDFs selecionados"` (sem listar todos)

Pastas são expandidas pelo Worker (`.rglob("*.pdf")`, filtra `_limpo` no stem).

---

## 5. Painel de log

`QPlainTextEdit` somente leitura, fonte monoespaçada, altura fixa ~140 px. Aparece (junto com a barra de progresso) quando o processamento inicia. Cada sinal `log(str)` anexa uma linha e rola automaticamente para o fim.

Formato das linhas de log:

```
[1/12] Limpando Processo_0123456.pdf...
[1/12] OCR página 4/18...
[1/12] Numerando páginas...
[2/12] Limpando Processo_0123457.pdf...
[AVISO] OCR falhou em página 7: timeout
Concluído. 24 arquivos gerados.
```

---

## 6. Conclusão e abertura de pasta

Após `terminou`:

- Status exibe `"Concluído. N arquivo(s) gerado(s)."` ou a mensagem de cancelamento
- Botão **"Abrir pasta LIMPOS"** aparece, chamando `QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta_saida)))`
- Erros fatais: `QMessageBox.critical(self, "Erro", msg)` — modal, UI retorna ao estado inicial após OK

---

## 7. Layout final (de cima para baixo)

```
Título + explicação
────────────────────────────────
[AreaDrop: botões + zona de drag]
Label de seleção
────────────────────────────────
☑ OCR   ☑ Paginar   ☑ Dividir [150 ▲▼ páginas]   ☑ Gerar .txt
────────────────────────────────
[         Limpar / Cancelar       ]
████████████░░░░░░░  62%   OCR página 8/18...
┌─ log ──────────────────────────┐
│ [1/3] Limpando proc_0001.pdf  │
│ [1/3] OCR página 4/18...      │
└────────────────────────────────┘
[Abrir pasta LIMPOS]   (aparece após conclusão)
```

---

## 8. Qt stylesheet (escopo mínimo)

| Elemento | Estilo |
|---|---|
| Botão "Limpar" | fundo `#003366`, texto branco, hover `#004488` |
| Botão "Cancelar" | fundo `#8b0000`, texto branco, hover `#a00000` |
| `QPlainTextEdit` log | fundo `#f5f5f5`, borda `1px solid #ddd` |
| Resto | padrão do sistema (Windows Fusion/native) |

Paleta mínima — evita surpresas em ambientes Windows gerenciados pelo ZenWorks.

---

## 9. O que NÃO muda

- Pipeline na ordem exata da seção 3 do CLAUDE.md: `limpa_pdf` → `embutir_ocr` → `numerar_paginas` → `dividir_pdf` → `exportar_txt`
- Pasta de saída fixa: `LIMPOS/` dentro da pasta de entrada (ou do pai do PDF)
- `sem_cabecalho=True` sempre ligado
- Operação 100% offline
- Arquivo único `gui.py` (sem módulos separados)
