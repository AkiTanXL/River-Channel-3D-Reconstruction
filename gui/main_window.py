"""
主窗口类
包含堆叠窗口、菜单栏和日志管理
"""

import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QStackedWidget, QGroupBox, QTextBrowser)
from PyQt5.QtGui import QFont, QTextCursor

from modules import Module0UI, Module1UI, Module2UI, Module3UI
from components import QPlainTextEditLogger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("稀疏剖面河道三维重建系统 - TanXL")
        self.resize(1200, 800)

        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)
        QApplication.setFont(font)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.stacked_widget = QStackedWidget()
        self.mod0_ui = Module0UI()
        self.mod1_ui = Module1UI()
        self.mod2_ui = Module2UI()
        self.mod3_ui = Module3UI()

        self.stacked_widget.addWidget(self.mod0_ui)
        self.stacked_widget.addWidget(self.mod1_ui)
        self.stacked_widget.addWidget(self.mod2_ui)
        self.stacked_widget.addWidget(self.mod3_ui)

        self.create_flat_menu()

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("background-color: #2b2b2b; color: #a9b7c6; font-family: Consolas;")
        log_layout.addWidget(self.log_browser)

        main_layout.addWidget(self.stacked_widget, 7)
        main_layout.addWidget(log_group, 3)

        self.setup_logging()

    def create_flat_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("background-color: #e0e0e0; font-weight: bold; padding: 5px;")

        actions = [
            ("模块0：数据预处理", 0),
            ("模块1：深泓点内插", 1),
            ("模块2：河岸点内插", 2),
            ("模块3：剖面点内插", 3)
        ]

        for name, index in actions:
            action = menubar.addAction(name)
            action.triggered.connect(lambda checked, idx=index: self.stacked_widget.setCurrentIndex(idx))

    def setup_logging(self):
        self.log_handler = QPlainTextEditLogger()
        self.log_handler.signaler.new_log.connect(self.append_log)

        rc3dr_logger = logging.getLogger('rc3dr')
        rc3dr_logger.setLevel(logging.INFO)
        rc3dr_logger.addHandler(self.log_handler)

        logging.info("系统初始化完成。欢迎使用 TanXL 稀疏剖面河道三维重建系统。")

    def append_log(self, msg):
        self.log_browser.append(msg)
        self.log_browser.moveCursor(QTextCursor.End)
