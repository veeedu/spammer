#!/usr/bin/env python3
# spm_V3.py
import sys
import time
import platform
import pyperclip
import pyautogui

from PyQt5.QtCore import (
    Qt, QTimer, QSettings, QObject, pyqtSignal, QThread, pyqtSlot
)
from PyQt5.QtGui import QIcon, QPixmap, QFont, QGuiApplication
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton,
    QProgressBar, QSystemTrayIcon, QMenu, QAction, QLineEdit, QSpinBox,
    QDoubleSpinBox, QHBoxLayout, QGroupBox, QTextEdit, QMessageBox, QSplashScreen
)

APP_NAME = "Clipboard Spammer"
ORG_NAME = "MyCompany"

# choose paste modifier based on platform
PASTE_KEY = "command" if platform.system() == "Darwin" else "ctrl"


# -------------------------
# Worker (runs in QThread)
# -------------------------
class SpamWorker(QObject):
    progress = pyqtSignal(int)       # 0-100 (or -1 for indeterminate)
    status = pyqtSignal(str)         # status text updates
    finished = pyqtSignal()          # when done / stopped

    def __init__(self, message, delay, repeat, start_delay):
        super().__init__()
        self.message = message
        self.delay = float(delay)
        self.repeat = int(repeat)
        self.start_delay = float(start_delay)
        self._stop_requested = False

    @pyqtSlot()
    def run(self):
        """Main worker loop. Emits progress/status/finished signals."""
        try:
            self.status.emit(f"Waiting {self.start_delay:.2f}s before start...")
            # start delay (allow stop during this time)
            waited = 0.0
            step = 0.05
            while waited < self.start_delay and not self._stop_requested:
                time.sleep(step)
                waited += step

            if self._stop_requested:
                self.status.emit("Stopped before start.")
                self.finished.emit()
                return

            # copy to clipboard once
            pyperclip.copy(self.message)
            self.status.emit("Spamming started (clipboard ready).")

            total = None if self.repeat == 0 else self.repeat
            count = 0

            # Loop
            while not self._stop_requested and (total is None or count < total):
                # paste via hotkey and press enter
                try:
                    pyautogui.hotkey(PASTE_KEY, 'v')
                    pyautogui.press('enter')
                except Exception as e:
                    # If pyautogui fails, notify status and stop
                    self.status.emit(f"Error using pyautogui: {e}")
                    break

                count += 1

                # emit progress: if finite, percent; else -1 for indeterminate/busy
                if total:
                    pct = int((count / total) * 100)
                    self.progress.emit(pct)
                    self.status.emit(f"Sent {count}/{total}")
                else:
                    # Indeterminate - signal -1
                    self.progress.emit(-1)
                    self.status.emit(f"Sent {count} (infinite)")

                # wait for delay but allow quick stop checks
                slept = 0.0
                step = 0.05
                while slept < self.delay and not self._stop_requested:
                    time.sleep(step)
                    slept += step

            if self._stop_requested:
                self.status.emit("Stopped by user.")
            else:
                self.status.emit("Completed.")
        finally:
            self.finished.emit()

    def stop(self):
        self._stop_requested = True


# -------------------------
# Splash / ModernSplash
# -------------------------
class ModernSplash(QSplashScreen):
    def __init__(self, splash_path, final_window=None):
        # load pixmap (fallback if missing)
        pix = QPixmap(splash_path)
        if pix.isNull():
            pix = QPixmap(600, 360)
            pix.fill(Qt.darkGray)

        # scale to reasonable size while keeping aspect ratio
        pix = pix.scaled(600, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        super().__init__(pix, Qt.WindowStaysOnTopHint)
        self.final_window = final_window
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowOpacity(0.0)

        # small overlay "glass" for progress region
        overlay_y = int(pix.height() * 0.72)
        overlay_h = pix.height() - overlay_y
        self.overlay = QLabel(self)
        self.overlay.setGeometry(0, overlay_y, pix.width(), overlay_h)
        # semi-transparent dark overlay to create acrylic look
        self.overlay.setStyleSheet("background: rgba(20,20,20,120); border-top: 1px solid rgba(255,255,255,40);")

        # progress bar (in lower half, centered)
        self.progress = QProgressBar(self)
        bar_w = pix.width() - 80
        self.progress.setGeometry(40, overlay_y + int(overlay_h * 0.35), bar_w, 14)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { background: rgba(0,0,0,60); border-radius:7px; border:1px solid rgba(255,255,255,20);}
            QProgressBar::chunk { background: #0077FF; border-radius:7px; }
        """)

        # status label
        self.label = QLabel("Starting...", self)
        self.label.setGeometry(0, overlay_y + int(overlay_h * 0.65), pix.width(), 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 12px;")

        # fade-in
        self._fade_in_anim()

    def _fade_in_anim(self):
        # simple incremental opacity (avoid extra Qt animation dependencies)
        self.setWindowOpacity(0.0)
        self.show()
        steps = 10
        for i in range(steps + 1):
            QTimer.singleShot(i * 30, lambda v=i: self.setWindowOpacity(v / steps))

    def set_status(self, text):
        self.label.setText(text)

    def set_progress(self, val):
        if val < 0:
            # indeterminate -> busy
            self.progress.setRange(0, 0)
        else:
            if self.progress.minimum() == 0 and self.progress.maximum() == 0:
                self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(val))))

    def finish_and_close(self, window):
        # fade out then close & show main window
        def do_finish():
            # short fade-out
            steps = 8
            for i in range(steps + 1):
                QTimer.singleShot(i * 30, lambda v=(steps - i) / steps: self.setWindowOpacity(v))
            QTimer.singleShot(steps * 30 + 50, lambda: (self.finish(window), window.show(), self.deleteLater()))
        QTimer.singleShot(150, do_finish)


# -------------------------
# Main Window
# -------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        # window icon (uses logo.ico)
        try:
            self.setWindowIcon(QIcon("logo.png"))
        except Exception:
            pass

        self.resize(700, 420)

        # settings
        self.settings = QSettings(ORG_NAME, APP_NAME)

        # UI elements
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # Logo header
        logo_label = QLabel()
        pix = QPixmap("logo.png")
        if pix.isNull():
            # try PNG fallback
            pix = QPixmap("logo.png")
        if not pix.isNull():
            logo_label.setPixmap(pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(logo_label)

        # Group box for spam inputs
        gb = QGroupBox("Spammer Settings")
        gb_layout = QVBoxLayout()
        gb.setLayout(gb_layout)

        # Message (multi-line)
        self.msg_edit = QTextEdit()
        self.msg_edit.setPlaceholderText("Message to send (supports multiple lines).")
        self.msg_edit.setFixedHeight(90)
        gb_layout.addWidget(self.msg_edit)

        # Row: delay, repeat, start delay
        row = QHBoxLayout()
        # Delay
        row.addWidget(QLabel("Delay (sec):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setDecimals(2)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setRange(0.01, 10000)
        row.addWidget(self.delay_spin)

        # Repeat
        row.addWidget(QLabel("Repeat (0 = infinite):"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(0, 100000000)
        row.addWidget(self.repeat_spin)

        # Start delay
        row.addWidget(QLabel("Start delay (sec):"))
        self.start_delay_spin = QDoubleSpinBox()
        self.start_delay_spin.setDecimals(2)
        self.start_delay_spin.setSingleStep(0.1)
        self.start_delay_spin.setRange(0, 60000)
        row.addWidget(self.start_delay_spin)

        gb_layout.addLayout(row)

        main_layout.addWidget(gb)

        # Controls: toggle button & status
        controls = QHBoxLayout()
        self.toggle_btn = QPushButton("▶ Start")
        self.toggle_btn.setFixedHeight(42)
        self.toggle_btn.clicked.connect(self.on_toggle)
        controls.addWidget(self.toggle_btn)

        self.theme_btn = QPushButton("Toggle Theme")
        self.theme_btn.setFixedHeight(42)
        self.theme_btn.clicked.connect(self.toggle_theme)
        controls.addWidget(self.theme_btn)

        main_layout.addLayout(controls)

        # Progress and status area
        self.main_progress = QProgressBar()
        self.main_progress.setRange(0, 100)
        self.main_progress.setValue(0)
        self.main_progress.setTextVisible(True)
        main_layout.addWidget(self.main_progress)

        self.status_label = QLabel("Ready.")
        main_layout.addWidget(self.status_label)

        # System tray icon
        self.tray = QSystemTrayIcon(QIcon("logo.ico"), self)
        tray_menu = QMenu()
        action_show = QAction("Show", self)
        action_show.triggered.connect(self.show)
        tray_menu.addAction(action_show)
        action_quit = QAction("Quit", self)
        action_quit.triggered.connect(self.close)
        tray_menu.addAction(action_quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.show()

        # Worker/thread holders
        self._worker = None
        self._thread = None

        # load settings
        self.load_settings()

        # theme state
        self._dark = self.settings.value("dark_mode", True, bool)
        self.apply_theme()

    # -------------------------
    # settings persistence
    # -------------------------
    def load_settings(self):
        self.msg_edit.setPlainText(self.settings.value("message", "", str))
        self.delay_spin.setValue(float(self.settings.value("delay", 0.5)))
        self.repeat_spin.setValue(int(self.settings.value("repeat", 0)))
        self.start_delay_spin.setValue(float(self.settings.value("start_delay", 1.0)))

    def save_settings(self):
        self.settings.setValue("message", self.msg_edit.toPlainText())
        self.settings.setValue("delay", float(self.delay_spin.value()))
        self.settings.setValue("repeat", int(self.repeat_spin.value()))
        self.settings.setValue("start_delay", float(self.start_delay_spin.value()))
        self.settings.setValue("dark_mode", self._dark)

    # -------------------------
    # theme handling (simple)
    # -------------------------
    def toggle_theme(self):
        self._dark = not self._dark
        self.apply_theme()

    def apply_theme(self):
        if self._dark:
            self.setStyleSheet("""
                QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #121212, stop:1 #262626); }
                QTextEdit, QSpinBox, QDoubleSpinBox, QLineEdit { background: #1e1e1e; color: #eee; border: 1px solid #333; }
                QLabel { color: #ddd; }
                QPushButton { background: #0071C5; color: white; padding: 6px; border-radius: 8px; }
                QPushButton:disabled { background: #444444; color: #ccc; }
                QGroupBox { color: #ddd; border: 1px solid rgba(255,255,255,0.04); border-radius: 8px; margin-top: 6px; padding: 8px; }
                QProgressBar { background: #2a2a2a; color: #fff; border-radius: 8px; }
                QProgressBar::chunk { background: #33a1ff; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f5f6f7, stop:1 #e6e7e8); }
                QTextEdit, QSpinBox, QDoubleSpinBox, QLineEdit { background: white; color: #111; border: 1px solid #ccc; }
                QLabel { color: #222; }
                QPushButton { background: #0071C5; color: white; padding: 6px; border-radius: 8px; }
                QPushButton:disabled { background: #dddddd; color: #888; }
                QGroupBox { color: #222; border: 1px solid rgba(0,0,0,0.06); border-radius: 8px; margin-top: 6px; padding: 8px; }
                QProgressBar { background: #f0f0f0; color: #111; border-radius: 8px; }
                QProgressBar::chunk { background: #0071C5; }
            """)

    # -------------------------
    # start / stop handling
    # -------------------------
    def on_toggle(self):
        if self._worker is None:
            # start
            msg = self.msg_edit.toPlainText().strip()
            if not msg:
                QMessageBox.warning(self, "No message", "Please enter the message to send.")
                return
            delay = float(self.delay_spin.value())
            repeat = int(self.repeat_spin.value())
            start_delay = float(self.start_delay_spin.value())

            # disable inputs
            self.msg_edit.setReadOnly(True)
            self.delay_spin.setEnabled(False)
            self.repeat_spin.setEnabled(False)
            self.start_delay_spin.setEnabled(False)
            self.toggle_btn.setText("⏹ Stop")
            self.toggle_btn.setStyleSheet("background: #bb2e2e; color: white;")

            # prepare worker & thread
            self._worker = SpamWorker(msg, delay, repeat, start_delay)
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            # connect signals
            self._thread.started.connect(self._worker.run)
            self._worker.progress.connect(self._on_progress)
            self._worker.status.connect(self._on_status)
            self._worker.finished.connect(self._on_finished)
            # start thread
            self._thread.start()
            # update UI
            self.status_label.setText("Queued...")
            self.main_progress.setValue(0)
            if repeat == 0:
                # show busy style
                self.main_progress.setRange(0, 0)
            else:
                self.main_progress.setRange(0, 100)

        else:
            # stop
            self.status_label.setText("Stopping...")
            self._worker.stop()
            # button will be re-enabled in _on_finished

    def _on_progress(self, val):
        # val == -1 => indeterminate
        if val < 0:
            self.main_progress.setRange(0, 0)
        else:
            if self.main_progress.maximum() == 0:
                self.main_progress.setRange(0, 100)
            self.main_progress.setValue(int(val))

    def _on_status(self, text):
        self.status_label.setText(text)

    def _on_finished(self):
        # cleanup worker and thread
        # call queued stop if needed
        try:
            if self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
        except Exception:
            pass

        self._worker = None
        self._thread = None

        # re-enable inputs
        self.msg_edit.setReadOnly(False)
        self.delay_spin.setEnabled(True)
        self.repeat_spin.setEnabled(True)
        self.start_delay_spin.setEnabled(True)
        self.toggle_btn.setText("▶ Start")
        self.toggle_btn.setStyleSheet("")  # fallback to theme style

        self.status_label.setText("Ready.")
        # keep progress bar at 100 if finite, or reset
        if self.main_progress.maximum() != 0:
            self.main_progress.setValue(100)
        else:
            self.main_progress.setRange(0, 100)
            self.main_progress.setValue(0)

    # -------------------------
    # clean close
    # -------------------------
    def closeEvent(self, event):
        # if running, stop worker
        if self._worker:
            self._worker.stop()
            # give a moment to stop
            if self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(1000)
        # save settings
        self.save_settings()
        event.accept()


# -------------------------
# Application startup
# -------------------------
def main():
    app = QApplication(sys.argv)
    # high-dpi scaling policy (optional)
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    # create main window
    window = MainWindow()

    # create splash and wire progress/status updates for aesthetics
    splash = ModernSplash("splash.png", final_window=window)

    # connect splash to show progress for a fake short sequence, then hand off:
    # We'll animate the splash for about 1s then show app
    # Use a simple timer to update splash progress smoothly
    steps = 100
    duration_ms = 1000
    step_ms = max(5, duration_ms // steps)
    current = 0

    def splash_step():
        nonlocal current
        current += 1
        # update splash bar and text
        splash.set_progress(int((current / steps) * 100))
        splash.set_status(f"Starting... {int((current/steps)*100)}%")
        if current >= steps:
            # finish
            splash.finish_and_close(window)
            splash.set_progress(100)
            splash.set_status("Ready")
            timer.stop()

    timer = QTimer()
    timer.timeout.connect(splash_step)
    timer.start(step_ms)

    # show splash (it's already shown in constructor), app exec
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
