# Limpa PDF — Especificação de Empacotamento (PyInstaller + Inno Setup)

**Data:** 2026-06-27
**Versão do core:** v2.6
**GUI:** gui.py (PySide6, validada em produção)

---

## 1. Objetivo

Gerar `LimpaPDF_setup.exe` — instalador silencioso para distribuição via ZenWorks no MPSC. O executável final deve rodar 100% offline, sem dependências externas (Python, Tesseract, tessdata).

---

## 2. Arquitetura

Pipeline de 4 etapas orquestradas por `build.ps1`:

```
build.ps1
  │
  ├─ 1. Preparação de assets
  │      icone.png → icone.ico  (Pillow, multi-tamanho: 16/32/48/64/128/256px)
  │      download por.traineddata tessdata_best → assets/tessdata_best/
  │      cópia osd.traineddata + pdf.ttf do Tesseract local → assets/tessdata_best/
  │
  ├─ 2. PyInstaller  →  dist/LimpaPDF/  (onedir, windowed)
  │      lê:  limpa_pdf.spec
  │
  ├─ 3. Inno Setup   →  dist/LimpaPDF_setup.exe
  │      lê:  installer.iss
  │
  └─ 4. Relatório: tamanho + SHA-256 do setup.exe
```

### Arquivos criados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `limpa_pdf.spec` | novo | Configuração declarativa PyInstaller |
| `installer.iss` | novo | Script Inno Setup |
| `build.ps1` | novo | Orquestrador do build |
| `assets/tessdata_best/` | gerado (gitignore) | tessdata_best + osd + pdf.ttf |
| `icone.ico` | gerado (gitignore) | Ícone multi-tamanho |
| `gui.py` | modificado | +~10 linhas: detecção de Tesseract bundled |

---

## 3. Tesseract embutido

**Instalação local:** `C:\Program Files\Tesseract-OCR\` (versão 5.5.0, ~89 MB, ~94 arquivos).

**O que entra no bundle:**

| Item | Origem | Destino no bundle |
|---|---|---|
| `tesseract.exe` | `C:\Program Files\Tesseract-OCR\` | `_internal/tesseract/` |
| `*.dll` (~60 arquivos) | `C:\Program Files\Tesseract-OCR\` | `_internal/tesseract/` |
| `por.traineddata` | tessdata_best (download ~12 MB) | `_internal/tesseract/tessdata/` |
| `osd.traineddata` | instalação local | `_internal/tesseract/tessdata/` |
| `pdf.ttf` | instalação local | `_internal/tesseract/tessdata/` |

**O que fica de fora:** `eng.traineddata`, utilitários (`combine_tessdata.exe`, etc.), HTMLs de documentação, JARs do ScrollView.

**Detecção de caminho em `gui.py`** — inserido no topo do módulo, antes de qualquer import de `core`:

```python
import sys, os
from pathlib import Path

if hasattr(sys, "_MEIPASS"):
    _tess = Path(sys._MEIPASS) / "tesseract"
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = str(_tess / "tesseract.exe")
    os.environ["TESSDATA_PREFIX"] = str(_tess / "tessdata")
```

Isso garante que `_preparar_ocr()` do core encontre o Tesseract bundled sem nenhuma modificação no módulo core.

---

## 4. PyInstaller spec (`limpa_pdf.spec`)

**Modo:** `onedir` + `windowed` (sem console, sem splash de descompactação).

**Razão do `onedir`:** `onefile` descompacta em `%TEMP%` a cada execução — mais lento e sujeito a bloqueio por antivírus em ambiente gerenciado.

**Binários do Tesseract:**
```python
binaries = [
    ("C:/Program Files/Tesseract-OCR/tesseract.exe", "tesseract"),
    ("C:/Program Files/Tesseract-OCR/*.dll", "tesseract"),
]
```

**Dados (tessdata_best):**
```python
datas = [
    ("assets/tessdata_best", "tesseract/tessdata"),
]
```

**Exclusões para reduzir tamanho:**
- PySide6: `QtWebEngine`, `QtWebEngineCore`, `QtWebEngineWidgets`, `QtMultimedia`, `Qt3D*`, `QtCharts`, `QtDataVisualization`, `QtLocation`, `QtQuick*`, `QtVirtual*`
- OpenCV: `cv2.gapi`, `cv2.cuda`

**Ícone:** `icone.ico` (gerado pelo build.ps1 antes de rodar PyInstaller).

**Risco/mitigação — conflito Qt plugins:** `opencv-python-headless` (não `opencv-python`) já está instalado, evitando colisão de `qwindows.dll`. Se mesmo assim houver conflito, excluir explicitamente plugins Qt do OpenCV no spec.

---

## 5. Inno Setup (`installer.iss`)

| Parâmetro | Valor |
|---|---|
| Nome exibido | `Limpa PDF — MPSC` |
| Versão | `2.6.0` |
| Publicador | `MPSC` |
| Destino | `{commonpf64}\LimpaPDF` (Program Files 64-bit) |
| Privilégios | `admin` (instalação por máquina) |
| Atalhos | Desktop + Menu Iniciar → `LimpaPDF.exe` |
| Ícone | `icone.ico` |
| Desinstalador | Sim (aparece em "Adicionar/Remover Programas") |

**Instalação silenciosa (ZenWorks):**
```
LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

**Code signing:** Fora do escopo deste ciclo. O `setup.exe` será não assinado. A assinatura digital pode ser aplicada após o build com `signtool.exe` quando a COTEC disponibilizar o certificado (ver CLAUDE.md §7).

---

## 6. Orquestrador (`build.ps1`)

Sequência idempotente — cada etapa verifica existência do artefato antes de refazer:

1. **Verificar pré-requisitos:** `python`, `pip` presentes; avisar se Inno Setup não instalado
2. **Instalar PyInstaller:** `pip install pyinstaller` (se ausente)
3. **Preparar assets:**
   - `icone.png` → `icone.ico` via Pillow (16/32/48/64/128/256px)
   - Download `por.traineddata` tessdata_best do GitHub releases → `assets/tessdata_best/`
   - Copiar `osd.traineddata` e `pdf.ttf` do Tesseract local
4. **Build PyInstaller:** `pyinstaller limpa_pdf.spec --noconfirm`; verificar `dist/LimpaPDF/LimpaPDF.exe`
5. **Build Inno Setup:** localizar `ISCC.exe` em `Program Files (x86)\Inno Setup 6\`; rodar `ISCC.exe installer.iss`; verificar `dist/LimpaPDF_setup.exe`
6. **Relatório:** tamanho do `setup.exe` + hash SHA-256

---

## 7. `.gitignore` — adições

```
assets/
icone.ico
dist/
build/
*.spec.bak
```

---

## 8. Restrições e decisões fechadas (CLAUDE.md §7)

- **`opencv-python-headless`** — nunca substituir por `opencv-python`; conflito de plugin Qt
- **`onedir`** — nunca `onefile`; antivírus bloqueia descompactação em `%TEMP%`
- **Program Files (por máquina)** — nunca instalação por usuário (`LOCALAPPDATA`)
- **100% offline** — `por.traineddata` baixado no build, não na primeira execução pelo usuário
- **Code signing:** fora do escopo; não bloqueia o build
