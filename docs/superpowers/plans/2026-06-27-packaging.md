# Limpa PDF — Empacotamento (PyInstaller + Inno Setup)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar `dist/LimpaPDF_setup.exe` — instalador silencioso para distribuição via ZenWorks, com Tesseract 5.5 e modelo tessdata_best em português embutidos.

**Architecture:** Quatro tarefas sequenciais: (1) adaptar `gui.py` para detectar Tesseract bundled e atualizar `.gitignore`; (2) escrever `limpa_pdf.spec` e validar o build PyInstaller; (3) escrever `installer.iss` e validar o build Inno Setup; (4) escrever `build.ps1` como orquestrador completo e idempotente.

**Tech Stack:** Python 3.13, PySide6 6.11, PyInstaller 6+, Inno Setup 6, opencv-python-headless 4.13, Tesseract 5.5.0 (tessdata_best), Pillow 12.

## Global Constraints

- **`onedir`** — nunca `onefile`; antivírus bloqueia descompactação em `%TEMP%` em ambiente gerenciado
- **`opencv-python-headless`** — nunca substituir por `opencv-python`; evita conflito de plugin Qt com PySide6
- **Destino do instalador:** `{commonpf64}\LimpaPDF` (Program Files 64-bit, por máquina, `admin`); nunca por usuário
- **100% offline em produção** — `por.traineddata` é baixado no build, nunca em tempo de execução pelo usuário
- **Tesseract bundled em `_internal/tesseract/`** — `tesseract.exe` + `*.dll` + `tessdata/por.traineddata` + `tessdata/osd.traineddata` + `tessdata/pdf.ttf`
- **`TESSDATA_PREFIX`** — deve apontar para o diretório PAI de `tessdata/` (ou seja, `_MEIPASS/tesseract`); o Tesseract acrescenta `/tessdata/` internamente
- **Ícone:** `icone.png` (1024×1024 RGBA, já na pasta do projeto) → `icone.ico` (16/32/48/64/128/256px via Pillow)
- **Nome:** `Limpa PDF — MPSC` | **Versão:** `2.6.0` | **Publisher:** `MPSC`
- **Gitignore:** `assets/`, `icone.ico`, `dist/`, `build/`, `*.spec.bak` devem ser ignorados
- **Code signing:** fora do escopo deste ciclo; não bloqueia o build

---

### Task 1: Adaptar gui.py para Tesseract bundled + atualizar .gitignore

**Files:**
- Modify: `gui.py` (inserir 7 linhas após `from pathlib import Path`, linha 29)
- Modify: `.gitignore` (adicionar 5 entradas de artefatos de build)

**Interfaces:**
- Consumes: nada de tasks anteriores
- Produces: `gui.py` com detecção de `sys._MEIPASS` que configura `pytesseract.tesseract_cmd` e `TESSDATA_PREFIX` antes de qualquer chamada ao core; `.gitignore` atualizado

- [ ] **Step 1: Verificar estado atual do .gitignore**

```powershell
Get-Content .gitignore
```

Expected:
```
__pycache__/
*.pyc
.superpowers/
.pytest_cache/
.claude/
```

- [ ] **Step 2: Adicionar entradas de build ao .gitignore**

Adicionar as linhas abaixo ao **final** do arquivo `.gitignore` (sem apagar as existentes):

```
assets/
icone.ico
dist/
build/
*.spec.bak
```

Arquivo final completo:
```
__pycache__/
*.pyc
.superpowers/
.pytest_cache/
.claude/
assets/
icone.ico
dist/
build/
*.spec.bak
```

- [ ] **Step 3: Confirmar imports atuais de gui.py**

```powershell
Get-Content gui.py | Select-Object -First 40
```

Confirmar que:
- Linha 28: `import sys`
- Linha 29: `from pathlib import Path`
- Linha 30: linha em branco
- Linha 31: `from PySide6.QtCore import Qt, QThread, Signal, QUrl`
- Linha 39: `import limpa_pdf_mpsc as core`
- `import os` ainda NÃO existe no arquivo

- [ ] **Step 4: Inserir bloco de detecção de Tesseract bundled em gui.py**

Localizar o trecho exato (linhas 29-31 do gui.py):
```python
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl
```

Substituir por:
```python
from pathlib import Path
import os

if hasattr(sys, "_MEIPASS"):
    _tess = Path(sys._MEIPASS) / "tesseract"
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = str(_tess / "tesseract.exe")
    os.environ["TESSDATA_PREFIX"] = str(_tess)

from PySide6.QtCore import Qt, QThread, Signal, QUrl
```

**Atenção:** `TESSDATA_PREFIX` aponta para `_tess` (o diretório `tesseract/`), NÃO para `_tess / "tessdata"`. O Tesseract internamente acrescenta `tessdata/` ao prefixo para encontrar os arquivos.

O topo de gui.py deve ficar assim após a edição:
```python
from __future__ import annotations

import sys
from pathlib import Path
import os

if hasattr(sys, "_MEIPASS"):
    _tess = Path(sys._MEIPASS) / "tesseract"
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = str(_tess / "tesseract.exe")
    os.environ["TESSDATA_PREFIX"] = str(_tess)

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QProgressBar, QFileDialog, QFrame, QPlainTextEdit,
    QMessageBox,
)

import limpa_pdf_mpsc as core
```

- [ ] **Step 5: Verificar que o bloco não quebra o import em dev**

```powershell
python -c "import gui; print('OK')"
```

Expected: `OK` (o bloco `if hasattr(sys, '_MEIPASS')` é False em dev, portanto não executa)

- [ ] **Step 6: Rodar suite de testes completa**

```powershell
python -m pytest tests/ -v
```

Expected:
```
10 passed in X.XXs
```

Nenhum teste deve quebrar — a mudança só ativa quando `sys._MEIPASS` existe (bundle frozen).

- [ ] **Step 7: Commit**

```powershell
git add gui.py .gitignore
git commit -m "feat: detectar Tesseract bundled via sys._MEIPASS; atualizar .gitignore para artefatos de build"
```

---

### Task 2: limpa_pdf.spec — build PyInstaller

**Files:**
- Create: `limpa_pdf.spec`

**Interfaces:**
- Consumes: `gui.py` com detecção de Tesseract (Task 1); `icone.ico` e `assets/tessdata_best/` preparados inline nesta task
- Produces: `dist/LimpaPDF/LimpaPDF.exe` executável standalone; estrutura `dist/LimpaPDF/_internal/tesseract/` com Tesseract embutido

- [ ] **Step 1: Instalar PyInstaller**

```powershell
pip install pyinstaller
```

Expected: `Successfully installed pyinstaller-X.X.X` ou `Requirement already satisfied`

Verificar versão (deve ser 6+):
```powershell
pyinstaller --version
```

- [ ] **Step 2: Preparar assets/tessdata_best/**

```powershell
New-Item -ItemType Directory -Force -Path "assets\tessdata_best" | Out-Null
```

Baixar `por.traineddata` do tessdata_best (~12 MB):
```powershell
$url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/por.traineddata"
Invoke-WebRequest -Uri $url -OutFile "assets\tessdata_best\por.traineddata"
```

Copiar `osd.traineddata` e `pdf.ttf` da instalação local do Tesseract:
```powershell
Copy-Item "C:\Program Files\Tesseract-OCR\tessdata\osd.traineddata" "assets\tessdata_best\"
Copy-Item "C:\Program Files\Tesseract-OCR\tessdata\pdf.ttf"         "assets\tessdata_best\"
```

Verificar:
```powershell
Get-ChildItem "assets\tessdata_best\"
```

Expected: 3 arquivos — `por.traineddata`, `osd.traineddata`, `pdf.ttf`

- [ ] **Step 3: Gerar icone.ico**

```powershell
python -c "
from PIL import Image
img = Image.open('icone.png').convert('RGBA')
img.save('icone.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('icone.ico gerado')
"
```

Expected: `icone.ico gerado`

- [ ] **Step 4: Criar limpa_pdf.spec**

Criar o arquivo `limpa_pdf.spec` com o seguinte conteúdo exato:

```python
# -*- mode: python ; coding: utf-8 -*-
# limpa_pdf.spec — configuração PyInstaller para o Limpa PDF (MPSC)
#
# Build: pyinstaller limpa_pdf.spec --noconfirm
# Pré-requisitos: assets/tessdata_best/ e icone.ico devem existir (build.ps1 os prepara)

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        ('C:/Program Files/Tesseract-OCR/tesseract.exe', 'tesseract'),
        ('C:/Program Files/Tesseract-OCR/*.dll',         'tesseract'),
    ],
    datas=[
        ('assets/tessdata_best', 'tesseract/tessdata'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtLocation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DLogic',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtNfc',
        'PySide6.QtBluetooth',
        'PySide6.QtSql',
        'PySide6.QtSerialPort',
        'PySide6.QtSerialBus',
        'PySide6.QtVirtualKeyboard',
        'cv2.gapi',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LimpaPDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='icone.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LimpaPDF',
)
```

**Por que `datas=[('assets/tessdata_best', 'tesseract/tessdata')]`:** PyInstaller copia os CONTEÚDOS de `assets/tessdata_best/` para `_MEIPASS/tesseract/tessdata/`. Com `TESSDATA_PREFIX = str(_MEIPASS / "tesseract")`, o Tesseract acrescenta `/tessdata/` e encontra os arquivos corretamente em `_MEIPASS/tesseract/tessdata/por.traineddata`.

- [ ] **Step 5: Rodar PyInstaller**

```powershell
pyinstaller limpa_pdf.spec --noconfirm
```

O processo leva 2-5 minutos. Saída esperada no final:
```
INFO: Building COLLECT COLLECT-00.toc completed successfully.
```

- [ ] **Step 6: Verificar artefatos gerados**

```powershell
Test-Path "dist\LimpaPDF\LimpaPDF.exe"
Test-Path "dist\LimpaPDF\_internal\tesseract\tesseract.exe"
Test-Path "dist\LimpaPDF\_internal\tesseract\tessdata\por.traineddata"
(Get-ChildItem "dist\LimpaPDF\_internal\tesseract\" -Filter "*.dll").Count
```

Expected:
```
True
True
True
<número > 0>   # deve haver dezenas de DLLs
```

- [ ] **Step 7: Testar lançamento do EXE**

```powershell
Start-Process "dist\LimpaPDF\LimpaPDF.exe"
Start-Sleep -Seconds 4
$proc = Get-Process -Name "LimpaPDF" -ErrorAction SilentlyContinue
if ($proc) { Write-Host "OK — janela aberta (PID $($proc.Id))"; $proc.CloseMainWindow() }
else        { Write-Host "FALHA — processo não encontrado" }
```

Expected: `OK — janela aberta (PID XXXXX)`

**Se a janela não abrir (conflito de Qt plugins):** é o risco conhecido de CLAUDE.md §7. Diagnóstico:
```powershell
Get-ChildItem -Recurse "dist\LimpaPDF\" -Filter "qwindows.dll" | Select-Object FullName
```
Se aparecer em mais de um caminho (ex: em `PySide6/plugins/` E em outro lugar), adicionar ao spec dentro de `excludes`:
```python
'PySide6.QtOpenGL',
'PySide6.QtOpenGLWidgets',
```
E re-rodar `pyinstaller limpa_pdf.spec --noconfirm`.

- [ ] **Step 8: Commit**

```powershell
git add limpa_pdf.spec
git commit -m "feat: PyInstaller spec (onedir, windowed, Tesseract 5.5 bundled, tessdata_best)"
```

---

### Task 3: installer.iss — build Inno Setup

**Files:**
- Create: `installer.iss`

**Interfaces:**
- Consumes: `dist\LimpaPDF\` (Task 2); `icone.ico` (Task 2)
- Produces: `dist\LimpaPDF_setup.exe` — instalador silencioso para ZenWorks

- [ ] **Step 1: Instalar Inno Setup 6**

```powershell
winget install JRSoftware.InnoSetup --silent
```

Expected: `Successfully installed` ou `No applicable update found` (já instalado).

Verificar instalação:
```powershell
Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

Expected: `True`

Se `winget` falhar, baixar o instalador do site oficial do Inno Setup (jrsoftware.org) e instalar manualmente. Após instalação, verificar novamente o caminho acima.

- [ ] **Step 2: Criar installer.iss**

Criar o arquivo `installer.iss` com o seguinte conteúdo exato:

```iss
; installer.iss — Inno Setup 6 para o Limpa PDF (MPSC)
; Build: ISCC.exe installer.iss
; Instalação silenciosa (ZenWorks): LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

[Setup]
AppName=Limpa PDF — MPSC
AppVersion=2.6.0
AppPublisher=MPSC
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
DefaultDirName={commonpf64}\LimpaPDF
DefaultGroupName=Limpa PDF
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=LimpaPDF_setup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\LimpaPDF.exe
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: checkedonce

[Files]
Source: "dist\LimpaPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Limpa PDF — MPSC"; Filename: "{app}\LimpaPDF.exe"
Name: "{group}\Desinstalar Limpa PDF"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Limpa PDF — MPSC"; Filename: "{app}\LimpaPDF.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LimpaPDF.exe"; Description: "Iniciar Limpa PDF — MPSC"; Flags: nowait postinstall skipifsilent
```

- [ ] **Step 3: Rodar ISCC**

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Expected no final:
```
Successful compile (0 error(s), X warning(s)).
```

- [ ] **Step 4: Verificar setup.exe**

```powershell
Test-Path "dist\LimpaPDF_setup.exe"
[math]::Round((Get-Item "dist\LimpaPDF_setup.exe").Length / 1MB, 1)
```

Expected: `True` e tamanho em MB (tipicamente 150–250 MB com tessdata_best embutido).

- [ ] **Step 5: Testar instalação silenciosa**

```powershell
Start-Process "dist\LimpaPDF_setup.exe" -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait
Test-Path "C:\Program Files\LimpaPDF\LimpaPDF.exe"
```

Expected: `True` — app instalado em Program Files.

Verificar atalho no Menu Iniciar:
```powershell
Test-Path "$env:PROGRAMDATA\Microsoft\Windows\Start Menu\Programs\Limpa PDF\Limpa PDF — MPSC.lnk"
```

Expected: `True`

- [ ] **Step 6: Testar que o app instalado abre**

```powershell
Start-Process "C:\Program Files\LimpaPDF\LimpaPDF.exe"
Start-Sleep -Seconds 4
$proc = Get-Process -Name "LimpaPDF" -ErrorAction SilentlyContinue
if ($proc) { Write-Host "OK — app instalado funciona (PID $($proc.Id))"; $proc.CloseMainWindow() }
else        { Write-Host "FALHA — processo não encontrado" }
```

Expected: `OK — app instalado funciona (PID XXXXX)`

- [ ] **Step 7: Desinstalar após o teste**

```powershell
$entry = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" |
         Where-Object { $_.DisplayName -like "*Limpa PDF*" }
if ($entry) {
    $uninstCmd = $entry.UninstallString -replace '"', ''
    Start-Process $uninstCmd -ArgumentList "/VERYSILENT /NORESTART" -Wait
    Write-Host "Desinstalado com sucesso"
} else {
    Write-Host "Entrada de desinstalação não encontrada no registro"
}
```

Expected: `Desinstalado com sucesso`

- [ ] **Step 8: Commit**

```powershell
git add installer.iss
git commit -m "feat: Inno Setup script (admin, Program Files 64-bit, BrazilianPortuguese, ZenWorks-ready)"
```

---

### Task 4: build.ps1 — orquestrador completo

**Files:**
- Create: `build.ps1`

**Interfaces:**
- Consumes: `limpa_pdf.spec` (Task 2), `installer.iss` (Task 3), `icone.png`, `gui.py` (Task 1)
- Produces: `dist/LimpaPDF_setup.exe` + relatório com tamanho e SHA-256; script idempotente (re-executar é seguro)

- [ ] **Step 1: Criar build.ps1**

Criar o arquivo `build.ps1` com o seguinte conteúdo exato:

```powershell
# build.ps1 — Orquestrador de build do Limpa PDF (MPSC)
# Uso: .\build.ps1
# Pré-requisitos: Python 3.13+, Inno Setup 6 instalado
# Artefato final: dist\LimpaPDF_setup.exe

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TESSERACT_DIR      = "C:\Program Files\Tesseract-OCR"
$TESSDATA_BEST_URL  = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/por.traineddata"
$ASSETS_DIR         = "assets\tessdata_best"
$ISCC               = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail([string]$msg)       { Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }

# ── 1. Pré-requisitos ────────────────────────────────────────────────────── #
Write-Step "Verificando pré-requisitos"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Fail "python nao encontrado no PATH" }
if (-not (Get-Command pip    -ErrorAction SilentlyContinue)) { Fail "pip nao encontrado no PATH" }
if (-not (Test-Path $TESSERACT_DIR)) { Fail "Tesseract nao encontrado em $TESSERACT_DIR" }
if (-not (Test-Path $ISCC))          { Fail "Inno Setup nao encontrado em $ISCC -- instale via: winget install JRSoftware.InnoSetup" }
if (-not (Test-Path "icone.png"))    { Fail "icone.png nao encontrado na pasta do projeto" }
if (-not (Test-Path "limpa_pdf.spec")) { Fail "limpa_pdf.spec nao encontrado" }
if (-not (Test-Path "installer.iss"))  { Fail "installer.iss nao encontrado" }

Write-Host "  OK" -ForegroundColor Green

# ── 2. PyInstaller ──────────────────────────────────────────────────────── #
Write-Step "Instalando PyInstaller (se necessario)"
pip install pyinstaller --quiet

# ── 3. Assets ────────────────────────────────────────────────────────────── #
Write-Step "Preparando assets"

# 3a. Icone
if (-not (Test-Path "icone.ico")) {
    Write-Host "  Convertendo icone.png -> icone.ico"
    python -c "
from PIL import Image
img = Image.open('icone.png').convert('RGBA')
img.save('icone.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('  icone.ico gerado')
"
} else {
    Write-Host "  icone.ico ja existe, pulando conversao"
}

# 3b. tessdata_best
New-Item -ItemType Directory -Force -Path $ASSETS_DIR | Out-Null

if (-not (Test-Path "$ASSETS_DIR\por.traineddata")) {
    Write-Host "  Baixando por.traineddata tessdata_best (~12 MB)..."
    Invoke-WebRequest -Uri $TESSDATA_BEST_URL -OutFile "$ASSETS_DIR\por.traineddata"
    Write-Host "  por.traineddata baixado"
} else {
    Write-Host "  por.traineddata ja existe, pulando download"
}

if (-not (Test-Path "$ASSETS_DIR\osd.traineddata")) {
    Write-Host "  Copiando osd.traineddata do Tesseract local"
    Copy-Item "$TESSERACT_DIR\tessdata\osd.traineddata" $ASSETS_DIR
} else {
    Write-Host "  osd.traineddata ja existe, pulando copia"
}

if (-not (Test-Path "$ASSETS_DIR\pdf.ttf")) {
    Write-Host "  Copiando pdf.ttf do Tesseract local"
    Copy-Item "$TESSERACT_DIR\tessdata\pdf.ttf" $ASSETS_DIR
} else {
    Write-Host "  pdf.ttf ja existe, pulando copia"
}

# ── 4. PyInstaller build ─────────────────────────────────────────────────── #
Write-Step "Build PyInstaller (onedir, windowed)"
pyinstaller limpa_pdf.spec --noconfirm

if (-not (Test-Path "dist\LimpaPDF\LimpaPDF.exe")) {
    Fail "dist\LimpaPDF\LimpaPDF.exe nao foi gerado -- verifique o log do PyInstaller acima"
}
Write-Host "  LimpaPDF.exe gerado" -ForegroundColor Green

# ── 5. Inno Setup build ──────────────────────────────────────────────────── #
Write-Step "Build Inno Setup (LimpaPDF_setup.exe)"
& $ISCC installer.iss

if (-not (Test-Path "dist\LimpaPDF_setup.exe")) {
    Fail "dist\LimpaPDF_setup.exe nao foi gerado -- verifique o log do ISCC acima"
}

# ── 6. Relatorio ─────────────────────────────────────────────────────────── #
Write-Step "Relatorio final"
$setupExe = Get-Item "dist\LimpaPDF_setup.exe"
$sizeMB   = [math]::Round($setupExe.Length / 1MB, 1)
$sha256   = (Get-FileHash $setupExe.FullName -Algorithm SHA256).Hash

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " BUILD CONCLUIDO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " Arquivo : $($setupExe.FullName)"
Write-Host " Tamanho : $sizeMB MB"
Write-Host " SHA-256 : $sha256"
Write-Host "========================================"
Write-Host ""
Write-Host "Instalacao silenciosa (ZenWorks):"
Write-Host "  LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
Write-Host ""
```

- [ ] **Step 2: Limpar artefatos anteriores para teste clean**

```powershell
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build, assets, icone.ico
```

- [ ] **Step 3: Rodar build.ps1 do zero**

```powershell
.\build.ps1
```

O processo completo leva 5-10 minutos: download ~12 MB + PyInstaller ~3 min + ISCC ~1 min.

Expected no final:
```
========================================
 BUILD CONCLUIDO
========================================
 Arquivo : C:\Users\...\dist\LimpaPDF_setup.exe
 Tamanho : XXX.X MB
 SHA-256 : <64 caracteres hex>
========================================

Instalacao silenciosa (ZenWorks):
  LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

- [ ] **Step 4: Verificar artefato final**

```powershell
Test-Path "dist\LimpaPDF_setup.exe"
[math]::Round((Get-Item "dist\LimpaPDF_setup.exe").Length / 1MB, 1)
```

Expected: `True` e tamanho em MB.

- [ ] **Step 5: Commit**

```powershell
git add build.ps1
git commit -m "feat: build.ps1 -- orquestrador completo idempotente (PyInstaller + Tesseract + Inno Setup)"
```
