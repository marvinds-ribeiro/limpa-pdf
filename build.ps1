# build.ps1 - Orquestrador de build do Limpa PDF (MPSC)
# Uso: .\build.ps1
# Pre-requisitos: Python 3.13+, Inno Setup 6 instalado
# Artefato final: dist\LimpaPDF_setup.exe

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TESSERACT_DIR      = "C:\Program Files\Tesseract-OCR"
$TESSDATA_BEST_URL  = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/por.traineddata"
$ASSETS_DIR         = "assets\tessdata_best"

# Deteccao dinamica do ISCC.exe (multiplos locais possiveis)
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$ISCC = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ISCC) { Write-Host "ERRO: Inno Setup nao encontrado - instale via: winget install JRSoftware.InnoSetup" -ForegroundColor Red; exit 1 }

function Write-Step([string]$msg) { Write-Host "
==> $msg" -ForegroundColor Cyan }
function Fail([string]$msg)       { Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }

# 1. Pre-requisitos
Write-Step "Verificando pre-requisitos"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Fail "python nao encontrado no PATH" }
if (-not (Get-Command pip    -ErrorAction SilentlyContinue)) { Fail "pip nao encontrado no PATH" }
if (-not (Test-Path $TESSERACT_DIR)) { Fail "Tesseract nao encontrado em $TESSERACT_DIR" }
if (-not (Test-Path "icone.png"))    { Fail "icone.png nao encontrado na pasta do projeto" }
if (-not (Test-Path "limpa_pdf.spec")) { Fail "limpa_pdf.spec nao encontrado" }
if (-not (Test-Path "installer.iss"))  { Fail "installer.iss nao encontrado" }

Write-Host "  OK" -ForegroundColor Green

# 2. PyInstaller
Write-Step "Instalando PyInstaller (se necessario)"
pip install pyinstaller --quiet

# 3. Assets
Write-Step "Preparando assets"

# 3a. Icone
if (-not (Test-Path "icone.ico")) {
    Write-Host "  Convertendo icone.png -> icone.ico"
    python -c @'
from PIL import Image
img = Image.open('icone.png').convert('RGBA')
img.save('icone.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('  icone.ico gerado')
'@
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

# 4. PyInstaller build
Write-Step "Build PyInstaller (onedir, windowed)"
pyinstaller limpa_pdf.spec --noconfirm

if (-not (Test-Path "dist\LimpaPDF\LimpaPDF.exe")) {
    Fail "dist\LimpaPDF\LimpaPDF.exe nao foi gerado -- verifique o log do PyInstaller acima"
}
Write-Host "  LimpaPDF.exe gerado" -ForegroundColor Green

if (-not (Test-Path "dist\LimpaPDF\_internal\tesseract\tesseract.exe")) {
    Fail "Tesseract nao foi incluido no bundle -- verifique o caminho em limpa_pdf.spec"
}

if (-not (Test-Path "dist\LimpaPDF\_internal\tesseract\tessdata\por.traineddata")) {
    Fail "por.traineddata nao foi incluido no bundle -- verifique assets\tessdata_best\"
}

# 5. Inno Setup build
Write-Step "Build Inno Setup (LimpaPDF_setup.exe)"
& $ISCC installer.iss

if (-not (Test-Path "dist\LimpaPDF_setup.exe")) {
    Fail "dist\LimpaPDF_setup.exe nao foi gerado -- verifique o log do ISCC acima"
}

# 6. Relatorio
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
