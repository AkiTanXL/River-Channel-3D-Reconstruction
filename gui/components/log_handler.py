"""
线程安全的日志重定向组件
"""

import logging
from PyQt5.QtCore import pyqtSignal, QObject


class LogSignal(QObject):
    new_log = pyqtSignal(str)


class QPlainTextEditLogger(logging.Handler):
    def __init__(self):
        super().__init__()
        self.signaler = LogSignal()
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        self.signaler.new_log.emit(msg)
