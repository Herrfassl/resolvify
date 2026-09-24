import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from . import core


class Worker(QThread):
    log = Signal(str)
    progress = Signal(int)  # overall, 0..1000
    finished_all = Signal()

    def __init__(self, files, out_dir, ffmpeg, ffprobe):
        super().__init__()
        self.files, self.out_dir, self.ffmpeg, self.ffprobe = files, out_dir, ffmpeg, ffprobe
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        n = len(self.files)
        for i, src in enumerate(self.files):
            if self._cancel:
                break
            dst = core.output_path(src, self.out_dir)
            if dst.exists():
                self.log.emit(f"skip (exists): {src.name}")
            else:
                self.log.emit(f"[{i + 1}/{n}] {src.name}")
                ok, msg = core.convert(
                    self.ffmpeg, self.ffprobe, src, dst,
                    on_progress=lambda f, i=i: self.progress.emit(int((i + f) / n * 1000)),
                    cancelled=lambda: self._cancel,
                )
                if not ok:
                    self.log.emit(f"  {'stopped' if msg == 'cancelled' else 'ERROR'}: {msg}")
            self.progress.emit(int((i + 1) / n * 1000))
        self.finished_all.emit()


class Window(QWidget):
    def __init__(self, ffmpeg, ffprobe):
        super().__init__()
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe
        self.out_dir = None
        self.worker = None
        self.setWindowTitle("resolvify")
        self.setAcceptDrops(True)
        self.resize(640, 480)

        self.list = QListWidget()
        self.hint = QLabel("Drop video files or folders here")
        self.out_label = QLabel()
        self._show_out()
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.logbox = QPlainTextEdit(readOnly=True)

        self.add_btn = QPushButton("Add files…")
        self.out_btn = QPushButton("Output folder…")
        self.clear_btn = QPushButton("Clear")
        self.start_btn = QPushButton("Start")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.pick_files)
        self.out_btn.clicked.connect(self.pick_out)
        self.clear_btn.clicked.connect(self.list.clear)
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(lambda: self.worker and self.worker.cancel())

        row = QHBoxLayout()
        for b in (self.add_btn, self.out_btn, self.clear_btn, self.start_btn, self.cancel_btn):
            row.addWidget(b)
        col = QVBoxLayout(self)
        for w in (self.hint, self.list, self.out_label, row, self.bar, self.logbox):
            col.addLayout(w) if w is row else col.addWidget(w)

    def _show_out(self):
        self.out_label.setText(f"Output: {self.out_dir or 'resolve/ next to each original'}")

    def add(self, paths):
        have = {self.list.item(i).text() for i in range(self.list.count())}
        for f in core.collect_videos(paths):
            if str(f) not in have:
                self.list.addItem(str(f))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.add([u.toLocalFile() for u in e.mimeData().urls()])

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add videos")
        self.add(files)

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder")
        if d:
            self.out_dir = d
            self._show_out()

    def start(self):
        files = [Path(self.list.item(i).text()) for i in range(self.list.count())]
        if not files:
            return
        self.bar.setValue(0)
        self.logbox.clear()
        self.worker = Worker(files, self.out_dir, self.ffmpeg, self.ffprobe)
        self.worker.log.connect(self.logbox.appendPlainText)
        self.worker.progress.connect(self.bar.setValue)
        self.worker.finished_all.connect(self.done)
        self._busy(True)
        self.worker.start()

    def done(self):
        self._busy(False)
        self.logbox.appendPlainText("done")

    def _busy(self, busy):
        for b in (self.add_btn, self.out_btn, self.clear_btn, self.start_btn):
            b.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        e.accept()


def main():
    app = QApplication(sys.argv)
    ffmpeg, ffprobe = core.find_tool("ffmpeg"), core.find_tool("ffprobe")
    if not (ffmpeg and ffprobe):
        QMessageBox.critical(None, "resolvify", "ffmpeg/ffprobe not found. Install ffmpeg and retry.")
        return 1
    w = Window(ffmpeg, ffprobe)
    w.show()
    return app.exec()
