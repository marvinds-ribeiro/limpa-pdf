@echo off
REM ============================================================
REM  Limpeza de PDFs do SIG (MPSC) - v2.4 + OCR
REM  Igual ao Limpar_PDFs.bat, mas tambem aplica OCR nas paginas
REM  SEM camada de texto, para que o .txt nao perca informacao.
REM  A camada de texto do OCR fica posicionada exatamente sobre a
REM  imagem (selecionavel e pesquisavel, alinhada ao que se ve).
REM  Requer o programa Tesseract (o script o encontra sozinho e
REM  baixa o idioma portugues se faltar). OCR a 300 dpi: ~3-6 s/pagina.
REM  v2.10: PDFs do e-proc/TJSC (scan + camada de texto do tribunal) sao
REM  tratados pelo flag --reocr-hibrido (padrao auto: reusa a camada boa e
REM  roda OCR proprio so quando ela e deficiente). Para forcar ou proibir:
REM    python limpa_pdf_mpsc.py <pasta> --reocr-hibrido sempre|nunca ...
REM ============================================================
if "%~1"=="" (
  echo Arraste uma pasta com PDFs ^(ou um PDF^) para cima deste arquivo.
  pause & exit /b
)
echo Verificando dependencias ^(so demora na 1a vez^)...
python -m pip install --quiet --disable-pip-version-check pikepdf pdfplumber pypdfium2 pytesseract pillow opencv-python-headless numpy
if errorlevel 1 (
  echo.
  echo [ERRO] Nao consegui instalar as bibliotecas. Verifique se o Python
  echo foi instalado com "Add python.exe to PATH" e se ha internet.
  pause & exit /b
)
echo Limpando PDFs de: %~1  ^(com OCR - pode demorar^)
python "%~dp0limpa_pdf_mpsc.py" "%~1" --sem-cabecalho --md --ocr
echo.
echo Fim. Se apareceu [OK] acima, os *_limpo.pdf e *_limpo.md estao prontos.
pause
