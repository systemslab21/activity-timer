#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QProgressBar,
    QVBoxLayout, QHBoxLayout, QDialog, QSpinBox, QFormLayout,
    QDialogButtonBox, QCheckBox,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
import io, math, os, struct, subprocess, tempfile, threading, wave

SIT_DEFAULT = 30   # minutes
ACT_DEFAULT = 5    # minutes

_SAMPLE_RATE = 44100


def _make_wav(freq: float, duration: float, volume: float) -> bytes:
    n = int(_SAMPLE_RATE * duration)
    fade = max(1, int(_SAMPLE_RATE * 0.01))
    samples = []
    for i in range(n):
        s = volume * math.sin(2 * math.pi * freq * i / _SAMPLE_RATE)
        if i < fade:
            s *= i / fade
        elif i > n - fade:
            s *= (n - i) / fade
        samples.append(int(s * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(struct.pack(f"<{n}h", *samples))
    return buf.getvalue()


def _play_tone(freq: float, duration: float = 0.2, volume: float = 0.6):
    data = _make_wav(freq, duration, volume)

    def _worker():
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            tmp = f.name
        try:
            for cmd in (["paplay", tmp], ["aplay", "-q", tmp]):
                try:
                    if subprocess.run(cmd, capture_output=True, timeout=4).returncode == 0:
                        return
                except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                    continue
        finally:
            os.unlink(tmp)

    threading.Thread(target=_worker, daemon=True).start()


SIT_COLOR = "#e94560"
ACT_COLOR = "#00b4d8"

STYLE = """
QWidget {
    background-color: #1a1a2e;
    color: #ffffff;
    font-family: "Segoe UI", "DejaVu Sans", sans-serif;
}
QPushButton {
    background-color: #16213e;
    color: #ffffff;
    border: none;
    padding: 5px 14px;
    border-radius: 4px;
    font-size: 9pt;
}
QPushButton:hover  { background-color: #0f3460; }
QPushButton:pressed { background-color: #0a2444; }
QProgressBar {
    border: none;
    background-color: #0d0d1a;
    border-radius: 4px;
}
QProgressBar::chunk { border-radius: 4px; }
QSpinBox {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #0f3460;
    padding: 2px 4px;
    border-radius: 3px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #0f3460;
    border: none;
}
"""


class SettingsDialog(QDialog):
    def __init__(self, parent, sit_min: int, act_min: int, sound: bool):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(230, 140)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)

        form = QFormLayout(self)
        form.setContentsMargins(16, 14, 16, 10)
        form.setSpacing(8)

        self.sit_spin = QSpinBox()
        self.sit_spin.setRange(1, 180)
        self.sit_spin.setValue(sit_min)
        self.sit_spin.setSuffix(" min")
        form.addRow("Sit duration:", self.sit_spin)

        self.act_spin = QSpinBox()
        self.act_spin.setRange(1, 60)
        self.act_spin.setValue(act_min)
        self.act_spin.setSuffix(" min")
        form.addRow("Active duration:", self.act_spin)

        self.sound_chk = QCheckBox()
        self.sound_chk.setChecked(sound)
        form.addRow("Sound alerts:", self.sound_chk)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> tuple[int, int, bool]:
        return self.sit_spin.value(), self.act_spin.value(), self.sound_chk.isChecked()


class ActivityTimer(QWidget):
    def __init__(self):
        super().__init__()
        self.sit_secs = SIT_DEFAULT * 60
        self.act_secs = ACT_DEFAULT * 60
        self.mode = "sitting"
        self.remaining = self.sit_secs
        self.running = False
        self.sound_enabled = True

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._refresh()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("Activity Timer")
        self.setFixedSize(290, 165)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(4)

        self.lbl_mode = QLabel()
        self.lbl_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mode.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        root.addWidget(self.lbl_mode)

        self.lbl_time = QLabel()
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setFont(QFont("Courier New", 38, QFont.Weight.Bold))
        self.lbl_time.setStyleSheet("color: #ffffff;")
        root.addWidget(self.lbl_time)

        self.pb = QProgressBar()
        self.pb.setTextVisible(False)
        self.pb.setFixedHeight(8)
        root.addWidget(self.pb)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 4, 0, 0)

        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.toggle)
        btn_row.addWidget(self.btn_start)

        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset)
        btn_row.addWidget(btn_reset)

        btn_cfg = QPushButton("Settings")
        btn_cfg.clicked.connect(self._open_settings)
        btn_row.addWidget(btn_cfg)

        root.addLayout(btn_row)

    # ── Timer logic ───────────────────────────────────────────────────────

    def toggle(self):
        if self.running:
            self.running = False
            self._timer.stop()
            self.btn_start.setText("Start")
        else:
            self.running = True
            self._timer.start()
            self.btn_start.setText("Stop")

    def reset(self):
        self.running = False
        self._timer.stop()
        self.btn_start.setText("Start")
        self.mode = "sitting"
        self.remaining = self.sit_secs
        self._refresh()

    def _tick(self):
        if self.remaining > 0:
            self.remaining -= 1
            self._refresh()
        else:
            self._next_mode()

    def _next_mode(self):
        self.mode = "active" if self.mode == "sitting" else "sitting"
        self.remaining = self.act_secs if self.mode == "active" else self.sit_secs
        self._refresh()
        self._alert()

    # ── Alerts ────────────────────────────────────────────────────────────

    def _alert(self):
        self.raise_()
        self.activateWindow()
        if self.sound_enabled:
            freq = 880 if self.mode == "active" else 523
            _play_tone(freq)
            QTimer.singleShot(250, lambda: _play_tone(freq))
        self._flash_title(6)

    def _flash_title(self, n: int):
        if n <= 0:
            self.setWindowTitle("Activity Timer")
            return
        msg = "TIME TO MOVE!" if self.mode == "active" else "BACK TO WORK"
        self.setWindowTitle(msg if n % 2 == 0 else "Activity Timer")
        QTimer.singleShot(500, lambda: self._flash_title(n - 1))

    # ── Display ───────────────────────────────────────────────────────────

    def _refresh(self):
        m, s = divmod(self.remaining, 60)
        self.lbl_time.setText(f"{m:02d}:{s:02d}")

        if self.mode == "sitting":
            total, color, label = self.sit_secs, SIT_COLOR, "SITTING"
        else:
            total, color, label = self.act_secs, ACT_COLOR, "MOVE!"

        self.lbl_mode.setStyleSheet(f"color: {color};")
        self.lbl_mode.setText(label)

        pct = int(100 - self.remaining / total * 100)
        self.pb.setValue(pct)
        self.pb.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
        )

    # ── Settings ──────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self, self.sit_secs // 60, self.act_secs // 60, self.sound_enabled)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sit_m, act_m, self.sound_enabled = dlg.values()
            self.sit_secs = sit_m * 60
            self.act_secs = act_m * 60
            self.reset()

    # ── Keyboard shortcuts ────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.toggle()
        elif event.key() in (Qt.Key.Key_R, Qt.Key.Key_Escape):
            self.reset()
        else:
            super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Activity Timer")
    win = ActivityTimer()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
