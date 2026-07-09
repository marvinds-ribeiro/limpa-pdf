#!/usr/bin/env python3
"""
gui.py — Interface gráfica do Limpa PDF (MPSC) — ESQUELETO v0.1

Casca visual em PySide6 sobre o núcleo de limpeza (limpa_pdf_mpsc.py).
NÃO reimplementa lógica: importa e chama as funções públicas do módulo, na
mesma ordem que o main() do CLI (ver CLAUDE.md §3 e o pipeline real).

Pipeline (idêntico ao main() do CLI):
    1. limpa_pdf(origem, destino, sem_cabecalho)
    2. embutir_ocr(destino, lang, cfg)            # se OCR ligado
    3. numerar_paginas(destino, total, inicio=1)  # se paginação ligada (PDF inteiro)
    4. dividir_pdf(destino, max_mb) -> [(parte, offset), ...]
    5. para cada parte: exportar_md(offset=offset, total=total)  # se .md ligado

Decisões (CLAUDE.md §7/§8):
    - PySide6 (LGPL), drag-and-drop nativo.
    - Processamento em QThread (a UI NUNCA congela durante lotes/OCR).
    - Progresso por sinal/slot; um callback é passado ao Worker.
    - opencv-python-headless já em uso (evita conflito de plugin Qt).

ESTADO: esqueleto funcional para iterar no Claude Code. Os pontos marcados
com  # TODO  são onde a lógica fina ainda precisa ser ligada/refinada.
"""

from __future__ import annotations

import sys
from pathlib import Path

# No app congelado (PyInstaller), a resolução do Tesseract embutido
# (exe + tessdata_best) é responsabilidade do core: _preparar_ocr() detecta
# sys._MEIPASS e configura tudo (vide limpa_pdf_mpsc._tessdata_embutido).

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QProgressBar, QFileDialog, QFrame, QPlainTextEdit,
    QMessageBox,
)

import limpa_pdf_mpsc as core


# ── 1. TEMA INSTITUCIONAL (explícito — NUNCA herda a paleta do sistema) ───── #
#
# O app roda em máquinas gerenciadas com Windows em modo claro OU escuro. Sem
# tema explícito, o Qt herda a paleta do sistema e o resultado quebra (ver
# prints/: checkboxes e barra vermelhos, texto branco do sistema sobre fundo
# claro fixo). Aqui TODAS as cores são fixadas — QPalette + QSS central — de
# modo que a janela seja idêntica nos dois modos do Windows.
#
# Paleta sóbria (ferramenta institucional do MPSC): fundos neutros claros,
# texto quase-preto, UM tom de destaque (azul institucional) para a ação
# principal; vermelho APENAS na ação destrutiva (cancelar processamento).
# Todos os pares texto/fundo abaixo atendem WCAG AA (>= 4.5:1) — verificado
# em tests/test_tema.py.

COR_FUNDO          = "#f4f5f7"  # fundo geral da janela
COR_SUPERFICIE     = "#ffffff"  # campos, log, área de seleção
COR_TEXTO          = "#1a1f24"  # texto principal (quase-preto)
COR_TEXTO_SUAVE    = "#5a626c"  # explicações e dicas
COR_BORDA          = "#c3c9d0"  # bordas de campos e separadores
COR_DESTAQUE       = "#003366"  # azul institucional — botão "Limpar"
COR_DESTAQUE_HOVER = "#004488"
COR_PERIGO         = "#8b0000"  # vermelho — SÓ p/ ação destrutiva (cancelar)
COR_PERIGO_HOVER   = "#a00000"
COR_BOTAO          = "#e8ebef"  # botões neutros (selecionar, abrir pasta)
COR_BOTAO_HOVER    = "#dde1e6"
COR_DESAB_FUNDO    = "#c9cdd2"  # controles desabilitados
COR_DESAB_TEXTO    = "#5d646b"
COR_BARRA_FUNDO    = "#e2e6ea"  # trilho da barra de progresso
# O preenchimento é um tom CLARO do azul institucional de propósito: o texto
# do percentual (preto) fica legível tanto sobre o trilho quanto sobre o
# preenchimento, em qualquer fração de progresso (AA nos dois fundos).
COR_BARRA_CHUNK    = "#a9c3dd"

TEMA_QSS = f"""
QWidget {{
    background-color: {COR_FUNDO};
    color: {COR_TEXTO};
}}
QLabel {{ background: transparent; }}
QLabel#explicacao {{ color: {COR_TEXTO_SUAVE}; }}
QLabel#hint_drop {{ color: {COR_TEXTO_SUAVE}; font-style: italic; border: none; }}
QLabel#lbl_entrada {{ color: {COR_TEXTO_SUAVE}; font-style: italic; }}
QLabel#lbl_entrada[definida="true"] {{ color: {COR_TEXTO}; font-style: normal; }}
QLabel#lbl_status {{ color: {COR_TEXTO}; background-color: {COR_FUNDO}; }}

QPushButton {{
    background-color: {COR_BOTAO};
    color: {COR_TEXTO};
    border: 1px solid {COR_BORDA};
    border-radius: 4px;
    padding: 6px 16px;
}}
QPushButton:hover {{ background-color: {COR_BOTAO_HOVER}; }}
QPushButton:disabled {{
    background-color: {COR_DESAB_FUNDO};
    color: {COR_DESAB_TEXTO};
    border-color: {COR_DESAB_FUNDO};
}}

QPushButton#btn_limpar {{
    background-color: {COR_DESTAQUE};
    color: #ffffff;
    border: none;
    font-size: 13px;
}}
QPushButton#btn_limpar:hover {{ background-color: {COR_DESTAQUE_HOVER}; }}
QPushButton#btn_limpar[modo="perigo"] {{ background-color: {COR_PERIGO}; }}
QPushButton#btn_limpar[modo="perigo"]:hover {{ background-color: {COR_PERIGO_HOVER}; }}
QPushButton#btn_limpar:disabled {{
    background-color: {COR_DESAB_FUNDO};
    color: {COR_DESAB_TEXTO};
}}

QCheckBox {{ background: transparent; color: {COR_TEXTO}; }}
QSpinBox {{
    background-color: {COR_SUPERFICIE};
    color: {COR_TEXTO};
    border: 1px solid {COR_BORDA};
    border-radius: 3px;
    padding: 2px 6px;
}}
QSpinBox:disabled {{ background-color: {COR_DESAB_FUNDO}; color: {COR_DESAB_TEXTO}; }}

QProgressBar {{
    background-color: {COR_BARRA_FUNDO};
    color: {COR_TEXTO};
    border: 1px solid {COR_BORDA};
    border-radius: 4px;
    text-align: center;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background-color: {COR_BARRA_CHUNK};
    border-radius: 3px;
}}

QPlainTextEdit#log_area {{
    background-color: {COR_SUPERFICIE};
    color: {COR_TEXTO};
    border: 1px solid {COR_BORDA};
    font-family: Consolas, 'Courier New', monospace;
    font-size: 9pt;
}}

QFrame#area_drop {{
    background-color: {COR_SUPERFICIE};
    border: 1px dashed {COR_BORDA};
    border-radius: 6px;
}}
QFrame#linha {{ color: {COR_BORDA}; }}

QToolTip {{
    background-color: {COR_SUPERFICIE};
    color: {COR_TEXTO};
    border: 1px solid {COR_BORDA};
}}
"""


def aplicar_tema(app: QApplication) -> None:
    """Aplica o tema claro institucional, EXPLÍCITO e completo: estilo Fusion
    (desenha com a QPalette, sem tema nativo do Windows), QPalette com todos
    os papéis fixados e a folha de estilo central TEMA_QSS. Com isso o visual
    é idêntico com o Windows em modo claro ou escuro — inclusive o indicador
    dos checkboxes (Highlight = azul institucional, nunca a cor do sistema)."""
    from PySide6.QtGui import QColor, QPalette

    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(COR_FUNDO))
    pal.setColor(QPalette.WindowText, QColor(COR_TEXTO))
    pal.setColor(QPalette.Base, QColor(COR_SUPERFICIE))
    pal.setColor(QPalette.AlternateBase, QColor(COR_BARRA_FUNDO))
    pal.setColor(QPalette.Text, QColor(COR_TEXTO))
    pal.setColor(QPalette.PlaceholderText, QColor(COR_TEXTO_SUAVE))
    pal.setColor(QPalette.Button, QColor(COR_BOTAO))
    pal.setColor(QPalette.ButtonText, QColor(COR_TEXTO))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.Highlight, QColor(COR_DESTAQUE))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.Link, QColor(COR_DESTAQUE))
    pal.setColor(QPalette.ToolTipBase, QColor(COR_SUPERFICIE))
    pal.setColor(QPalette.ToolTipText, QColor(COR_TEXTO))
    for papel in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, papel, QColor(COR_DESAB_TEXTO))
    app.setPalette(pal)
    app.setStyleSheet(TEMA_QSS)


def _repolir(w) -> None:
    """Reaplica o QSS após mudança de propriedade dinâmica (ex.: [modo])."""
    w.style().unpolish(w)
    w.style().polish(w)


def _coletar_arquivos(entradas: list[Path]) -> list[tuple[Path, Path]]:
    """Expande pastas recursivamente; retorna (arquivo, pasta_saida) sem duplicatas."""
    vistos: set[Path] = set()
    resultado: list[tuple[Path, Path]] = []
    for entrada in entradas:
        if entrada.is_dir():
            base = entrada / "LIMPOS"
            candidatos = sorted(entrada.rglob("*.pdf"))
        else:
            base = entrada.parent / "LIMPOS"
            candidatos = [entrada]
        for arq in candidatos:
            if "_limpo" not in arq.stem and arq not in vistos:
                vistos.add(arq)
                resultado.append((arq, base))
    return resultado


# ── 2. WORKER ─────────────────────────────────────────────────────────────── #


class Worker(QThread):
    progresso = Signal(int, str)
    log      = Signal(str)
    terminou = Signal(list, bool)   # (arquivos_gerados, cancelado)
    erro     = Signal(str)

    _cancelar: bool = False

    def __init__(self, entradas: list[Path], opcoes: dict):
        super().__init__()
        self.entradas = entradas
        self.opcoes = opcoes

    def requisitar_cancelamento(self) -> None:
        self._cancelar = True

    def run(self):
        try:
            self._executar()
        except Exception as e:
            self.erro.emit(str(e))

    def _executar(self):
        op = self.opcoes
        pares = _coletar_arquivos(self.entradas)
        if not pares:
            self.erro.emit("Nenhum PDF encontrado.")
            return

        lang, cfg = "", ""
        if op["ocr"]:
            self.progresso.emit(0, "Localizando o motor de OCR (Tesseract)...")
            lang, cfg = core._preparar_ocr()
            if not lang:
                self.log.emit("[AVISO] OCR indisponível; seguindo sem OCR.")

        gerados: list[str] = []
        total = len(pares)

        for k, (arq, pasta_saida) in enumerate(pares):
            if self._cancelar:
                break

            pct = int(k / total * 100)
            msg = f"[{k+1}/{total}] Limpando {arq.name}..."
            self.progresso.emit(pct, msg)
            self.log.emit(msg)

            pasta_saida.mkdir(parents=True, exist_ok=True)
            destino = pasta_saida / arq.name
            core.limpa_pdf(arq, destino, op["sem_cabecalho"])

            if self._cancelar:
                break

            info_ocr = {}
            if lang:
                msg = f"[{k+1}/{total}] OCR em {arq.name} (pode demorar)..."
                self.progresso.emit(pct, msg)
                self.log.emit(msg)
                try:
                    _n_ocr, info_ocr = core.embutir_ocr(destino, lang, cfg)
                except Exception as e:
                    self.log.emit(f"[AVISO] OCR falhou: {e}")

                if self._cancelar:
                    break

            # Total de páginas do PDF limpo (já com OCR): usado pela paginação
            # carimbada e pelo "## Página N de TOTAL" do .md.
            total_pag = 0
            try:
                import pikepdf
                with pikepdf.open(destino) as _p:
                    total_pag = len(_p.pages)
            except Exception:
                pass

            if op["paginar"] and total_pag:
                self.log.emit(f"[{k+1}/{total}] Numerando páginas de {arq.name}...")
                try:
                    core.numerar_paginas(destino, total_pag, inicio=1)
                except Exception as e:
                    self.log.emit(f"[AVISO] Numeração falhou: {e}")

            max_mb = op["max_mb"] if op["dividir"] else 0
            try:
                partes = core.dividir_pdf(destino, max_mb)
            except Exception:
                partes = [(destino, 1)]

            for parte, offset in partes:
                gerados.append(parte.name)
                if op["md"]:
                    md = parte.with_suffix(".md")
                    try:
                        core.exportar_md(parte, md, offset=offset,
                                         total=total_pag, info_ocr=info_ocr)
                        if md.is_file():
                            gerados.append(md.name)
                    except Exception as e:
                        self.log.emit(f"[AVISO] .md falhou: {e}")

        cancelado = self._cancelar
        if cancelado:
            self.log.emit(
                f"Cancelado. {len(gerados)} arquivo(s) gerado(s) antes do cancelamento."
            )
        else:
            self.progresso.emit(100, "Concluído.")
            self.log.emit(f"Concluído. {len(gerados)} arquivo(s) gerado(s).")

        self.terminou.emit(gerados, cancelado)


# ── 3. WIDGETS AUXILIARES ─────────────────────────────────────────────────── #


class AreaDrop(QFrame):
    """Zona de seleção e drag-and-drop; emite entrada_definida(list[Path])."""

    entrada_definida = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("area_drop")   # estilizado no TEMA_QSS central
        self._montar()

    def _montar(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        botoes = QHBoxLayout()
        btn_pasta = QPushButton("Selecionar pasta")
        btn_pdfs  = QPushButton("Selecionar PDF(s)")
        btn_pasta.clicked.connect(self._escolher_pasta)
        btn_pdfs.clicked.connect(self._escolher_pdfs)
        botoes.addWidget(btn_pasta)
        botoes.addWidget(btn_pdfs)
        lay.addLayout(botoes)

        hint = QLabel("ou arraste pastas e PDFs aqui")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("hint_drop")   # estilizado no TEMA_QSS central
        lay.addWidget(hint)

    def _escolher_pasta(self):
        d = QFileDialog.getExistingDirectory(self, "Escolha a pasta com os PDFs")
        if d:
            self.entrada_definida.emit([Path(d)])

    def _escolher_pdfs(self):
        fs, _ = QFileDialog.getOpenFileNames(
            self, "Escolha PDF(s)", filter="PDF (*.pdf)"
        )
        if fs:
            self.entrada_definida.emit([Path(f) for f in fs])

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [
            Path(url.toLocalFile())
            for url in e.mimeData().urls()
            if Path(url.toLocalFile()).is_dir()
            or Path(url.toLocalFile()).suffix.lower() == ".pdf"
        ]
        if paths:
            self.entrada_definida.emit(paths)


EXPLICACAO = (
    "Prepara procedimentos exportados do SIG para uso em ferramentas de "
    "inteligência artificial. Remove cabeçalhos e rodapés, apaga a assinatura "
    "digital da lateral e o carimbo de cópia e, opcionalmente, reconhece o texto "
    "de páginas escaneadas (OCR). Tudo no seu computador, sem enviar nada para a "
    "internet."
)


# ── 4. JANELA PRINCIPAL ───────────────────────────────────────────────────── #


class JanelaPrincipal(QWidget):
    def __init__(self):
        super().__init__()
        self.entradas: list[Path] = []
        self.worker: Worker | None = None
        self._processando: bool = False
        self._pasta_saida: Path | None = None
        self.setWindowTitle("Limpa PDF — MPSC")
        self.setMinimumWidth(580)
        self._montar()

    # ── layout ────────────────────────────────────────────────────────────── #
    def _montar(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        titulo = QLabel("Limpa PDF")
        f = QFont(); f.setPointSize(20); f.setBold(True)
        titulo.setFont(f)
        lay.addWidget(titulo)

        expl = QLabel(EXPLICACAO)
        expl.setWordWrap(True)
        expl.setObjectName("explicacao")
        lay.addWidget(expl)

        lay.addWidget(self._linha())

        self.area_drop = AreaDrop()
        self.area_drop.entrada_definida.connect(self._on_entrada_definida)
        lay.addWidget(self.area_drop)

        self.lbl_entrada = QLabel(
            "Nenhuma seleção  ·  (você também pode arrastar para a área acima)"
        )
        self.lbl_entrada.setObjectName("lbl_entrada")
        self.lbl_entrada.setProperty("definida", "false")
        lay.addWidget(self.lbl_entrada)

        lay.addWidget(self._linha())

        self.box_opcoes = QFrame()
        op = QVBoxLayout(self.box_opcoes)
        op.setSpacing(8)

        self.chk_ocr = QCheckBox("Reconhecer texto de páginas escaneadas (OCR) — mais lento")
        self.chk_pag = QCheckBox("Numerar as páginas (recomendado para citar páginas à IA)")
        self.chk_md = QCheckBox("Gerar arquivo de texto (.md) para colar na IA")
        # OCR ligado por padrão (v2.8): a finalidade do programa é EXTRAIR o
        # conteúdo para IA — sem OCR, prints e páginas escaneadas se perdem.
        self.chk_ocr.setChecked(True)
        self.chk_pag.setChecked(True)
        self.chk_md.setChecked(True)

        div = QHBoxLayout()
        self.chk_div = QCheckBox("Dividir PDFs grandes em partes de no máximo")
        self.chk_div.setChecked(True)
        self.spin_mb = QSpinBox()
        self.spin_mb.setRange(5, 5000)
        self.spin_mb.setValue(core.MAX_MB_PARTE)
        self.spin_mb.setSuffix(" MB")
        self.chk_div.toggled.connect(self.spin_mb.setEnabled)
        div.addWidget(self.chk_div)
        div.addWidget(self.spin_mb)
        div.addStretch()

        op.addWidget(self.chk_ocr)
        op.addWidget(self.chk_pag)
        op.addLayout(div)
        op.addWidget(self.chk_md)
        self.box_opcoes.setEnabled(False)
        lay.addWidget(self.box_opcoes)

        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.setObjectName("btn_limpar")
        self.btn_limpar.setMinimumHeight(40)
        self.btn_limpar.setEnabled(False)
        self.btn_limpar.clicked.connect(self._on_btn_limpar)
        lay.addWidget(self.btn_limpar)

        self.barra = QProgressBar()
        self.barra.setValue(0)
        self.barra.hide()
        lay.addWidget(self.barra)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("lbl_status")
        lay.addWidget(self.lbl_status)

        self.log_area = QPlainTextEdit()
        self.log_area.setObjectName("log_area")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(140)
        self.log_area.hide()
        lay.addWidget(self.log_area)

        self.btn_abrir = QPushButton("Abrir pasta LIMPOS")
        self.btn_abrir.clicked.connect(self._abrir_pasta)
        self.btn_abrir.hide()
        lay.addWidget(self.btn_abrir)

        lay.addStretch()

    def _linha(self) -> QFrame:
        ln = QFrame()
        ln.setFrameShape(QFrame.HLine)
        ln.setObjectName("linha")
        return ln

    # ── seleção de entrada ─────────────────────────────────────────────────── #
    def _on_entrada_definida(self, paths: list):
        self.entradas = [p if isinstance(p, Path) else Path(p) for p in paths]
        if len(self.entradas) == 1:
            p = self.entradas[0]
            tipo = "Pasta" if p.is_dir() else "PDF"
            self.lbl_entrada.setText(f"{tipo} selecionado: {p}")
        else:
            self.lbl_entrada.setText(f"{len(self.entradas)} PDFs selecionados")
        self.lbl_entrada.setProperty("definida", "true")
        _repolir(self.lbl_entrada)
        self.box_opcoes.setEnabled(True)
        self.btn_limpar.setEnabled(True)

    # ── execução ───────────────────────────────────────────────────────────── #
    def _on_btn_limpar(self):
        if self._processando:
            self._cancelar_worker()
        else:
            self._iniciar()

    def _iniciar(self):
        if not self.entradas:
            return
        opcoes = {
            "ocr":           self.chk_ocr.isChecked(),
            "paginar":       self.chk_pag.isChecked(),
            "dividir":       self.chk_div.isChecked(),
            "max_mb":        self.spin_mb.value(),
            "md":            self.chk_md.isChecked(),
            "sem_cabecalho": True,
        }
        self._processando = True
        self._pasta_saida = None
        self.btn_limpar.setText("Cancelar")
        self._marcar_botao_perigo(True)
        self.area_drop.setEnabled(False)
        self.box_opcoes.setEnabled(False)
        self.barra.show()
        self.barra.setValue(0)
        self.lbl_status.setText("")
        self.log_area.clear()
        self.log_area.show()
        self.btn_abrir.hide()

        self.worker = Worker(self.entradas, opcoes)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.log.connect(self._on_log)
        self.worker.terminou.connect(self._on_terminou)
        self.worker.erro.connect(self._on_erro)
        self.worker.start()

    def _cancelar_worker(self):
        if self.worker:
            self.worker.requisitar_cancelamento()
        self.btn_limpar.setEnabled(False)
        self.lbl_status.setText("Cancelando... aguarde o arquivo atual terminar.")

    # ── slots de sinal ─────────────────────────────────────────────────────── #
    def _on_progresso(self, pct: int, texto: str):
        self.barra.setValue(pct)
        self.lbl_status.setText(texto)

    def _on_log(self, linha: str):
        self.log_area.appendPlainText(linha)

    def _on_terminou(self, gerados: list, cancelado: bool):
        self._restaurar_ui()
        n = len(gerados)
        if cancelado:
            self.lbl_status.setText(
                f"Cancelado. {n} arquivo(s) gerado(s) antes do cancelamento."
            )
        else:
            self.lbl_status.setText(f"Concluído. {n} arquivo(s) gerado(s).")
            if self.entradas:
                primeiro = self.entradas[0]
                pasta = (primeiro if primeiro.is_dir() else primeiro.parent) / "LIMPOS"
                if pasta.is_dir():
                    self._pasta_saida = pasta
                    self.btn_abrir.show()

    def _on_erro(self, msg: str):
        self._restaurar_ui()
        QMessageBox.critical(self, "Erro", msg)
        self.lbl_status.setText("Erro. Verifique os arquivos e tente novamente.")

    def _marcar_botao_perigo(self, perigo: bool):
        """Alterna o botão principal entre ação (azul) e destrutiva (vermelho)
        via propriedade dinâmica [modo] — as cores vivem no TEMA_QSS central."""
        self.btn_limpar.setProperty("modo", "perigo" if perigo else "acao")
        _repolir(self.btn_limpar)

    def _restaurar_ui(self):
        self._processando = False
        self.area_drop.setEnabled(True)
        self.box_opcoes.setEnabled(bool(self.entradas))
        self.btn_limpar.setEnabled(True)
        self.btn_limpar.setText("Limpar")
        self._marcar_botao_perigo(False)

    def _abrir_pasta(self):
        if self._pasta_saida and self._pasta_saida.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._pasta_saida)))


def main():
    app = QApplication(sys.argv)
    aplicar_tema(app)
    win = JanelaPrincipal()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
