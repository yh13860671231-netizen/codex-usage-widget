"""AI Coding Radar V0.1
Minimal runnable prototype.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel


class RadarWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Coding Radar")
        self.resize(420, 300)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("AI Coding Radar - AI编程资源驾驶舱"))
        layout.addWidget(QLabel("🔥 火山 Coding Plan: 72%"))
        layout.addWidget(QLabel("🟣 Zcode: 58%"))
        layout.addWidget(QLabel("🔴 Codex账号A: 35%"))
        layout.addWidget(QLabel("🔴 Codex账号B: 86%"))
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = RadarWindow()
    w.show()
    sys.exit(app.exec())
