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
    4. dividir_pdf(destino, max_pag) -> [(parte, offset), ...]
    5. para cada parte: _detectar_tabelas_imagens + exportar_txt(offset=offset)  # se TXT

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

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QProgressBar, QFileDialog, QFrame, QPlainTextEdit,
    QMessageBox,
)

import limpa_pdf_mpsc as core


# ── 1. CONSTANTES E ESTILOS ──────────────────────────────────────────────── #


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


ESTILO_BTN_LIMPAR = (
    "QPushButton { background-color: #003366; color: white; border-radius: 4px;"
    " padding: 6px 16px; font-size: 13px; }"
    "QPushButton:hover { background-color: #004488; }"
    "QPushButton:disabled { background-color: #aaa; color: #eee; }"
)
ESTILO_BTN_CANCELAR = (
    "QPushButton { background-color: #8b0000; color: white; border-radius: 4px;"
    " padding: 6px 16px; font-size: 13px; }"
    "QPushButton:hover { background-color: #a00000; }"
    "QPushButton:disabled { background-color: #aaa; color: #eee; }"
)
APP_STYLESHEET = (
    "QPlainTextEdit#log_area {"
    "  background-color: #f5f5f5;"
    "  border: 1px solid #ddd;"
    "  font-family: Consolas, 'Courier New', monospace;"
    "  font-size: 9pt;"
    "}"
)


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

            if lang:
                msg = f"[{k+1}/{total}] OCR em {arq.name} (pode demorar)..."
                self.progresso.emit(pct, msg)
                self.log.emit(msg)
                try:
                    core.embutir_ocr(destino, lang, cfg)
                except Exception as e:
                    self.log.emit(f"[AVISO] OCR falhou: {e}")

                if self._cancelar:
                    break

            if op["paginar"]:
                self.log.emit(f"[{k+1}/{total}] Numerando páginas de {arq.name}...")
                try:
                    import pikepdf
                    with pikepdf.open(destino) as _p:
                        total_pag = len(_p.pages)
                    core.numerar_paginas(destino, total_pag, inicio=1)
                except Exception as e:
                    self.log.emit(f"[AVISO] Numeração falhou: {e}")

            max_pag = op["max_pag"] if op["dividir"] else 0
            try:
                partes = core.dividir_pdf(destino, max_pag)
            except Exception:
                partes = [(destino, 1)]

            for parte, offset in partes:
                gerados.append(parte.name)
                if op["txt"]:
                    txt = parte.with_suffix(".txt")
                    try:
                        avisos = core._detectar_tabelas_imagens(parte)
                    except Exception:
                        avisos = {}
                    try:
                        core.exportar_txt(parte, txt, avisos, offset=offset)
                        if txt.is_file():
                            gerados.append(txt.name)
                    except Exception as e:
                        self.log.emit(f"[AVISO] TXT falhou: {e}")

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
        self.setStyleSheet(
            "QFrame { border: 1px dashed #bbb; border-radius: 6px; }"
        )
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
        hint.setStyleSheet("color: #999; font-style: italic; border: none;")
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
        expl.setStyleSheet("color: #555;")
        lay.addWidget(expl)

        lay.addWidget(self._linha())

        self.area_drop = AreaDrop()
        self.area_drop.entrada_definida.connect(self._on_entrada_definida)
        lay.addWidget(self.area_drop)

        self.lbl_entrada = QLabel(
            "Nenhuma seleção  ·  (você também pode arrastar para a área acima)"
        )
        self.lbl_entrada.setStyleSheet("color: #777; font-style: italic;")
        lay.addWidget(self.lbl_entrada)

        lay.addWidget(self._linha())

        self.box_opcoes = QFrame()
        op = QVBoxLayout(self.box_opcoes)
        op.setSpacing(8)

        self.chk_ocr = QCheckBox("Reconhecer texto de páginas escaneadas (OCR) — mais lento")
        self.chk_pag = QCheckBox("Numerar as páginas (recomendado para citar páginas à IA)")
        self.chk_txt = QCheckBox("Gerar arquivo de texto (.txt) para colar na IA")
        self.chk_pag.setChecked(True)
        self.chk_txt.setChecked(True)

        div = QHBoxLayout()
        self.chk_div = QCheckBox("Dividir PDFs grandes em partes de")
        self.chk_div.setChecked(True)
        self.spin_pag = QSpinBox()
        self.spin_pag.setRange(1, 9999)
        self.spin_pag.setValue(core.MAX_PAGINAS)
        self.spin_pag.setSuffix(" páginas")
        self.chk_div.toggled.connect(self.spin_pag.setEnabled)
        div.addWidget(self.chk_div)
        div.addWidget(self.spin_pag)
        div.addStretch()

        op.addWidget(self.chk_ocr)
        op.addWidget(self.chk_pag)
        op.addLayout(div)
        op.addWidget(self.chk_txt)
        self.box_opcoes.setEnabled(False)
        lay.addWidget(self.box_opcoes)

        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.setMinimumHeight(40)
        self.btn_limpar.setEnabled(False)
        self.btn_limpar.setStyleSheet(ESTILO_BTN_LIMPAR)
        self.btn_limpar.clicked.connect(self._on_btn_limpar)
        lay.addWidget(self.btn_limpar)

        self.barra = QProgressBar()
        self.barra.setValue(0)
        self.barra.hide()
        lay.addWidget(self.barra)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #555;")
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
        ln.setStyleSheet("color: #ddd;")
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
        self.lbl_entrada.setStyleSheet("color: #222;")
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
            "max_pag":       self.spin_pag.value(),
            "txt":           self.chk_txt.isChecked(),
            "sem_cabecalho": True,
        }
        self._processando = True
        self._pasta_saida = None
        self.btn_limpar.setText("Cancelar")
        self.btn_limpar.setStyleSheet(ESTILO_BTN_CANCELAR)
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

    def _restaurar_ui(self):
        self._processando = False
        self.area_drop.setEnabled(True)
        self.box_opcoes.setEnabled(bool(self.entradas))
        self.btn_limpar.setEnabled(True)
        self.btn_limpar.setText("Limpar")
        self.btn_limpar.setStyleSheet(ESTILO_BTN_LIMPAR)

    def _abrir_pasta(self):
        if self._pasta_saida and self._pasta_saida.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._pasta_saida)))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    win = JanelaPrincipal()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
