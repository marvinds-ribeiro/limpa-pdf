"""Tema institucional EXPLÍCITO da GUI (não herda a paleta do sistema).

Reproduz o defeito de prints/visual escuro com texto fundo ilegivel.bmp:
com o Windows em modo escuro, o app herdava a paleta do sistema — checkboxes
e barra de progresso vermelhos, status quase invisível e o log com texto
branco (herdado) sobre fundo branco (fixo). O tema agora é 100% explícito:
QPalette clara + QSS central, idênticos em Windows claro ou escuro.
"""
import re
import sys

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

import gui


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


# --- contraste WCAG ----------------------------------------------------------

def _lum(hex_cor: str) -> float:
    """Luminância relativa (WCAG 2.x) de uma cor #rrggbb."""
    h = hex_cor.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(frente: str, fundo: str) -> float:
    l1, l2 = sorted((_lum(frente), _lum(fundo)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def test_pares_de_cor_atendem_wcag_aa():
    pares = [
        (gui.COR_TEXTO, gui.COR_FUNDO),          # texto geral
        (gui.COR_TEXTO, gui.COR_SUPERFICIE),     # texto em campos/log
        (gui.COR_TEXTO_SUAVE, gui.COR_FUNDO),    # explicações/dicas
        (gui.COR_TEXTO, gui.COR_BOTAO),          # botões neutros
        ("#ffffff", gui.COR_DESTAQUE),           # botão Limpar (ação)
        ("#ffffff", gui.COR_PERIGO),             # botão Cancelar (destrutiva)
        (gui.COR_TEXTO, gui.COR_BARRA_FUNDO),    # % sobre o trilho da barra
        (gui.COR_TEXTO, gui.COR_BARRA_CHUNK),    # % sobre o preenchimento
    ]
    for frente, fundo in pares:
        razao = _contraste(frente, fundo)
        assert razao >= 4.5, f"{frente} sobre {fundo}: {razao:.2f} < 4.5"


# --- paleta explícita --------------------------------------------------------

def test_paleta_explicita_clara_independente_do_sistema(qapp):
    gui.aplicar_tema(qapp)
    pal = qapp.palette()
    assert pal.color(QPalette.Window).name() == gui.COR_FUNDO
    assert pal.color(QPalette.WindowText).name() == gui.COR_TEXTO
    assert pal.color(QPalette.Base).name() == gui.COR_SUPERFICIE
    assert pal.color(QPalette.Text).name() == gui.COR_TEXTO
    assert pal.color(QPalette.Button).name() == gui.COR_BOTAO
    assert pal.color(QPalette.ButtonText).name() == gui.COR_TEXTO
    # o realce (checkbox marcado, seleção) é o azul institucional, nunca a
    # cor de destaque do sistema (vermelha no print do defeito)
    assert pal.color(QPalette.Highlight).name() == gui.COR_DESTAQUE
    assert pal.color(QPalette.HighlightedText).name() == "#ffffff"


# --- QSS central -------------------------------------------------------------

def _bloco(seletor: str) -> str:
    m = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", gui.TEMA_QSS)
    assert m, f"seletor ausente no TEMA_QSS: {seletor}"
    return m.group(1)


def test_status_tem_texto_e_fundo_explicitos():
    b = _bloco("QLabel#lbl_status")
    assert "color" in b and "background" in b


def test_barra_de_progresso_explicita_texto_fundo_e_chunk():
    b = _bloco("QProgressBar")
    assert "color" in b            # cor do texto do percentual
    assert "background" in b       # trilho
    assert "text-align" in b       # alinhamento do texto na barra
    chunk = _bloco("QProgressBar::chunk")
    assert "background" in chunk


def test_log_area_fixa_texto_e_fundo():
    # o defeito original: fundo claro FIXO com cor de texto HERDADA (branca
    # no Windows escuro) -> branco sobre branco
    b = _bloco("QPlainTextEdit#log_area")
    assert "color" in b and "background" in b


# --- janela usa o tema -------------------------------------------------------

def test_janela_liga_widgets_aos_seletores_do_tema(qapp):
    j = gui.JanelaPrincipal()
    assert j.lbl_status.objectName() == "lbl_status"
    assert j.log_area.objectName() == "log_area"
    assert j.btn_limpar.objectName() == "btn_limpar"
    # nenhum stylesheet local nos widgets do defeito: o tema é CENTRAL
    assert j.lbl_status.styleSheet() == ""
    assert j.barra.styleSheet() == ""
    assert j.log_area.styleSheet() == ""


def test_botao_alterna_para_perigo_por_propriedade(qapp):
    j = gui.JanelaPrincipal()
    assert j.btn_limpar.property("modo") != "perigo"
    j.entradas = [gui.Path(".")]
    # simula início de processamento sem disparar o worker de verdade
    j._processando = True
    j._marcar_botao_perigo(True)
    assert j.btn_limpar.property("modo") == "perigo"
    j._marcar_botao_perigo(False)
    assert j.btn_limpar.property("modo") != "perigo"
