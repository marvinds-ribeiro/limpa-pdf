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
