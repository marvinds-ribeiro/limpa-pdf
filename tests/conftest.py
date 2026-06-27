"""
Stub PySide6 antes de qualquer import de gui.py, para que os testes de lógica
pura (como _coletar_arquivos) rodem sem Qt instalado.
"""
import sys
from unittest.mock import MagicMock

for _mod in [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]:
    sys.modules.setdefault(_mod, MagicMock())
