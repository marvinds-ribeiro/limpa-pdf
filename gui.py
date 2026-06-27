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

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QProgressBar, QFileDialog, QFrame, QSizePolicy,
)

# O núcleo. Renomeie o arquivo final para limpa_pdf_mpsc.py (sem acento/sufixo).
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


# --------------------------------------------------------------------------- #
#  Worker: roda o pipeline numa thread separada para não travar a janela.
# --------------------------------------------------------------------------- #
class Worker(QThread):
    progresso = Signal(int, str)   # (porcentagem 0-100, texto de status)
    terminou = Signal(list)        # lista de arquivos gerados
    erro = Signal(str)             # mensagem de erro fatal

    def __init__(self, entrada: Path, opcoes: dict):
        super().__init__()
        self.entrada = entrada
        self.opcoes = opcoes       # {ocr, paginar, dividir, max_pag, txt, sem_cabecalho}

    def run(self):
        try:
            self._executar()
        except Exception as e:                       # rede de segurança
            self.erro.emit(str(e))

    def _executar(self):
        op = self.opcoes
        entrada = self.entrada

        # 1) Reúne os PDFs (pasta -> recursivo; arquivo -> ele mesmo).
        if entrada.is_dir():
            arquivos = sorted(entrada.rglob("*.pdf"))
        else:
            arquivos = [entrada]
        arquivos = [a for a in arquivos if "_limpo" not in a.stem]
        if not arquivos:
            self.erro.emit("Nenhum PDF encontrado.")
            return

        # 2) OCR: localiza Tesseract/idioma UMA vez (caro). lang vazio => sem OCR.
        lang, cfg = ("", "")
        if op["ocr"]:
            self.progresso.emit(0, "Localizando o motor de OCR (Tesseract)...")
            lang, cfg = core._preparar_ocr()
            if not lang:
                self.progresso.emit(0, "[aviso] OCR indisponível; seguindo sem OCR.")

        base_saida = (entrada if entrada.is_dir() else entrada.parent) / "LIMPOS"
        base_saida.mkdir(parents=True, exist_ok=True)

        gerados: list[str] = []
        total_arq = len(arquivos)

        for k, arq in enumerate(arquivos):
            pct_base = int(k / total_arq * 100)
            self.progresso.emit(pct_base, f"Limpando {arq.name}...")

            destino = base_saida / arq.name
            n = core.limpa_pdf(arq, destino, op["sem_cabecalho"])

            # OCR (se ligado e disponível)
            if lang:
                self.progresso.emit(pct_base, f"OCR em {arq.name} (pode demorar)...")
                try:
                    core.embutir_ocr(destino, lang, cfg)
                except Exception as e:
                    self.progresso.emit(pct_base, f"[aviso] OCR falhou: {e}")

            # Paginação contínua — sobre o PDF INTEIRO, ANTES de dividir.
            if op["paginar"]:
                self.progresso.emit(pct_base, f"Numerando páginas de {arq.name}...")
                try:
                    import pikepdf
                    with pikepdf.open(destino) as _p:
                        total_pag = len(_p.pages)
                    core.numerar_paginas(destino, total_pag, inicio=1)
                except Exception as e:
                    self.progresso.emit(pct_base, f"[aviso] numeração falhou: {e}")

            # Divisão — max_pag=0 significa "não dividir".
            max_pag = op["max_pag"] if op["dividir"] else 0
            try:
                partes = core.dividir_pdf(destino, max_pag)
            except Exception:
                partes = [(destino, 1)]

            # TXT por parte, com offset (numeração contínua entre partes).
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
                        self.progresso.emit(pct_base, f"[aviso] TXT falhou: {e}")

        self.progresso.emit(100, "Concluído.")
        self.terminou.emit(gerados)


# --------------------------------------------------------------------------- #
#  Janela principal.
# --------------------------------------------------------------------------- #
EXPLICACAO = (
    "Prepara procedimentos exportados do SIG para uso em ferramentas de "
    "inteligência artificial. Remove cabeçalhos e rodapés, apaga a assinatura "
    "digital da lateral e o carimbo de cópia e, opcionalmente, reconhece o texto "
    "de páginas escaneadas (OCR). Tudo no seu computador, sem enviar nada para a "
    "internet."
)


class JanelaPrincipal(QWidget):
    def __init__(self):
        super().__init__()
        self.entrada: Path | None = None
        self.worker: Worker | None = None
        self.setWindowTitle("Limpa PDF — MPSC")
        self.setAcceptDrops(True)               # drag-and-drop na janela inteira
        self.setMinimumWidth(560)
        self._montar()

    # ---- layout ----------------------------------------------------------- #
    def _montar(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        titulo = QLabel("Limpa PDF")
        f = QFont(); f.setPointSize(20); f.setBold(True)
        titulo.setFont(f)
        lay.addWidget(titulo)

        expl = QLabel(EXPLICACAO)
        expl.setWordWrap(True)
        expl.setStyleSheet("color: #555;")
        lay.addWidget(expl)

        lay.addWidget(self._linha())

        # --- seleção de entrada ---
        sel = QHBoxLayout()
        self.btn_pasta = QPushButton("Selecionar pasta")
        self.btn_pdf = QPushButton("Selecionar PDF")
        self.btn_pasta.clicked.connect(self._escolher_pasta)
        self.btn_pdf.clicked.connect(self._escolher_pdf)
        sel.addWidget(self.btn_pasta)
        sel.addWidget(self.btn_pdf)
        lay.addLayout(sel)

        self.lbl_entrada = QLabel("Nenhuma seleção  ·  (você também pode arrastar para esta janela)")
        self.lbl_entrada.setStyleSheet("color: #777; font-style: italic;")
        lay.addWidget(self.lbl_entrada)

        # --- opções (só habilitam após selecionar) ---
        self.box_opcoes = QFrame()
        op = QVBoxLayout(self.box_opcoes)
        op.setSpacing(8)

        self.chk_ocr = QCheckBox("Reconhecer texto de páginas escaneadas (OCR) — mais lento")
        self.chk_pag = QCheckBox("Numerar as páginas (recomendado para citar páginas à IA)")
        self.chk_txt = QCheckBox("Gerar arquivo de texto (.txt) para colar na IA")
        self.chk_pag.setChecked(True)            # padrões (CLAUDE.md §8)
        self.chk_txt.setChecked(True)

        div = QHBoxLayout()
        self.chk_div = QCheckBox("Dividir PDFs grandes em partes de")
        self.chk_div.setChecked(True)
        self.spin_pag = QSpinBox()
        self.spin_pag.setRange(1, 9999)
        self.spin_pag.setValue(core.MAX_PAGINAS)   # padrão 150, vindo do núcleo
        self.spin_pag.setSuffix(" páginas")
        self.chk_div.toggled.connect(self.spin_pag.setEnabled)
        div.addWidget(self.chk_div)
        div.addWidget(self.spin_pag)
        div.addStretch()

        op.addWidget(self.chk_ocr)
        op.addWidget(self.chk_pag)
        op.addLayout(div)
        op.addWidget(self.chk_txt)
        self.box_opcoes.setEnabled(False)        # desabilitado até haver entrada
        lay.addWidget(self.box_opcoes)

        # --- ação ---
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.setMinimumHeight(40)
        self.btn_limpar.setEnabled(False)
        self.btn_limpar.clicked.connect(self._iniciar)
        lay.addWidget(self.btn_limpar)

        # --- progresso ---
        self.barra = QProgressBar()
        self.barra.setValue(0)
        self.barra.hide()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #555;")
        lay.addWidget(self.barra)
        lay.addWidget(self.lbl_status)

        lay.addStretch()

    def _linha(self) -> QFrame:
        ln = QFrame(); ln.setFrameShape(QFrame.HLine)
        ln.setStyleSheet("color: #ddd;")
        return ln

    # ---- seleção ---------------------------------------------------------- #
    def _escolher_pasta(self):
        d = QFileDialog.getExistingDirectory(self, "Escolha a pasta com os PDFs")
        if d:
            self._definir_entrada(Path(d))

    def _escolher_pdf(self):
        f, _ = QFileDialog.getOpenFileName(self, "Escolha um PDF", filter="PDF (*.pdf)")
        if f:
            self._definir_entrada(Path(f))

    def _definir_entrada(self, p: Path):
        self.entrada = p
        tipo = "Pasta" if p.is_dir() else "Arquivo"
        self.lbl_entrada.setText(f"{tipo} selecionado:  {p}")
        self.lbl_entrada.setStyleSheet("color: #222;")
        self.box_opcoes.setEnabled(True)
        self.btn_limpar.setEnabled(True)

    # ---- drag-and-drop ---------------------------------------------------- #
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if not urls:
            return
        p = Path(urls[0].toLocalFile())          # TODO: aceitar múltiplos itens
        if p.is_dir() or p.suffix.lower() == ".pdf":
            self._definir_entrada(p)

    # ---- execução --------------------------------------------------------- #
    def _iniciar(self):
        if not self.entrada:
            return
        opcoes = {
            "ocr": self.chk_ocr.isChecked(),
            "paginar": self.chk_pag.isChecked(),
            "dividir": self.chk_div.isChecked(),
            "max_pag": self.spin_pag.value(),
            "txt": self.chk_txt.isChecked(),
            "sem_cabecalho": True,               # sempre ligado no fluxo atual (§8)
        }
        self._travar_ui(True)
        self.barra.show(); self.barra.setValue(0)

        self.worker = Worker(self.entrada, opcoes)
        self.worker.progresso.connect(self._on_progresso)
        self.worker.terminou.connect(self._on_terminou)
        self.worker.erro.connect(self._on_erro)
        self.worker.start()

    def _on_progresso(self, pct: int, texto: str):
        self.barra.setValue(pct)
        self.lbl_status.setText(texto)

    def _on_terminou(self, gerados: list):
        self._travar_ui(False)
        self.lbl_status.setText(f"Concluído. {len(gerados)} arquivo(s) gerado(s).")
        # TODO: botão "Abrir pasta de saída" (QDesktopServices.openUrl).

    def _on_erro(self, msg: str):
        self._travar_ui(False)
        self.lbl_status.setText(f"Erro: {msg}")

    def _travar_ui(self, travado: bool):
        for w in (self.btn_pasta, self.btn_pdf, self.btn_limpar, self.box_opcoes):
            w.setEnabled(not travado)


def main():
    app = QApplication(sys.argv)
    win = JanelaPrincipal()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
