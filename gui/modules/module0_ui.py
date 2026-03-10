"""
模块0：数据预处理UI
"""

import sys
import os
import geopandas as gpd
from PyQt5.QtWidgets import QLabel, QPushButton, QComboBox, QMessageBox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
try:
    import module0_data_preprocessing as mod0
except ImportError as e:
    print(f"Import backend module failed: {e}")

from base import BaseModuleUI
from components import WorkerThread


class Module0UI(BaseModuleUI):
    def __init__(self):
        super().__init__("模块0：数据预处理")

        self.preview_group.hide()

        self.in_shore = self.add_file_row(self.input_layout, 0, "河岸线 (.shp):", "../data/raw_data/河岸线.shp")
        self.in_bank = self.add_file_row(self.input_layout, 1, "实测河岸点 (.shp):", "../data/raw_data/实测河岸点.shp")
        self.in_prof = self.add_file_row(self.input_layout, 2, "剖面点 (.shp):", "../data/raw_data/剖面点.shp")

        self.out_shore = self.add_file_row(self.output_layout, 0, "河岸线 (.shp):",
                                           "../data/intermediate_data/河岸线.shp", False)
        self.out_polygon = self.add_file_row(self.output_layout, 1, "河道边界 (.shp):",
                                              "../data/intermediate_data/河道边界.shp", False)
        self.out_lbank = self.add_file_row(self.output_layout, 2, "左河岸点 (.shp):",
                                            "../data/intermediate_data/左河岸点.shp", False)
        self.out_rbank = self.add_file_row(self.output_layout, 3, "右河岸点 (.shp):",
                                            "../data/intermediate_data/右河岸点.shp", False)
        self.out_prof = self.add_file_row(self.output_layout, 4, "剖面点 (.shp):",
                                           "../data/intermediate_data/剖面点.shp", False)

        self.load_fields_btn = QPushButton("读取字段")
        self.load_fields_btn.clicked.connect(self.load_fields)
        self.param_layout.addWidget(self.load_fields_btn, 0, 0, 1, 2)

        self.param_layout.addWidget(QLabel("河岸点 X 字段:"), 1, 0)
        self.bank_x = QComboBox()
        self.param_layout.addWidget(self.bank_x, 1, 1)

        self.param_layout.addWidget(QLabel("河岸点 Y 字段:"), 2, 0)
        self.bank_y = QComboBox()
        self.param_layout.addWidget(self.bank_y, 2, 1)

        self.param_layout.addWidget(QLabel("河岸点 Z 字段:"), 3, 0)
        self.bank_z = QComboBox()
        self.param_layout.addWidget(self.bank_z, 3, 1)

        self.param_layout.addWidget(QLabel("剖面点 X 字段:"), 4, 0)
        self.prof_x = QComboBox()
        self.param_layout.addWidget(self.prof_x, 4, 1)

        self.param_layout.addWidget(QLabel("剖面点 Y 字段:"), 5, 0)
        self.prof_y = QComboBox()
        self.param_layout.addWidget(self.prof_y, 5, 1)

        self.param_layout.addWidget(QLabel("剖面点 Z 字段:"), 6, 0)
        self.prof_z = QComboBox()
        self.param_layout.addWidget(self.prof_z, 6, 1)

        self.param_layout.addWidget(QLabel("剖面ID字段:"), 7, 0)
        self.prof_id = QComboBox()
        self.param_layout.addWidget(self.prof_id, 7, 1)

        self.run_btn.clicked.connect(self.run_module)

    def load_fields(self):
        try:
            bank_file = self.in_bank.text()
            prof_file = self.in_prof.text()

            bank_gdf = gpd.read_file(bank_file)
            prof_gdf = gpd.read_file(prof_file)

            bank_fields = list(bank_gdf.columns)
            prof_fields = list(prof_gdf.columns)

            self.bank_x.clear()
            self.bank_y.clear()
            self.bank_z.clear()

            self.prof_x.clear()
            self.prof_y.clear()
            self.prof_z.clear()
            self.prof_id.clear()

            self.bank_x.addItems(bank_fields)
            self.bank_y.addItems(bank_fields)
            self.bank_z.addItems(bank_fields)

            self.prof_x.addItems(prof_fields)
            self.prof_y.addItems(prof_fields)
            self.prof_z.addItems(prof_fields)
            self.prof_id.addItems(prof_fields)

            self.auto_select_field(self.bank_x, ["东坐标", "x", "X"])
            self.auto_select_field(self.bank_y, ["北坐标", "y", "Y"])
            self.auto_select_field(self.bank_z, ["高程", "z", "Z"])

            self.auto_select_field(self.prof_x, ["东坐标", "x", "X"])
            self.auto_select_field(self.prof_y, ["北坐标", "y", "Y"])
            self.auto_select_field(self.prof_z, ["水底大", "z", "Z"])
            self.auto_select_field(self.prof_id, ["Type", "ID", "id"])

            QMessageBox.information(self, "成功", "字段读取成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段失败:\n{e}")

    def auto_select_field(self, combo, candidates):
        for name in candidates:
            idx = combo.findText(name)
            if idx != -1:
                combo.setCurrentIndex(idx)
                return

    def run_module(self):
        self.run_btn.setEnabled(False)

        try:
            self.thread = WorkerThread(
                mod0.preprocess_data,

                self.in_shore.text(),
                self.in_bank.text(),
                self.in_prof.text(),

                self.out_shore.text(),
                self.out_lbank.text(),
                self.out_rbank.text(),
                self.out_prof.text(),
                self.out_polygon.text(),

                self.bank_x.currentText(),
                self.bank_y.currentText(),
                self.bank_z.currentText(),

                self.prof_x.currentText(),
                self.prof_y.currentText(),
                self.prof_z.currentText(),

                self.prof_id.currentText()
            )

            self.thread.finished.connect(self.on_finished)
            self.thread.error.connect(self.on_error)
            self.thread.start()

        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
            self.run_btn.setEnabled(True)

    def on_finished(self):
        self.run_btn.setEnabled(True)
        QMessageBox.information(self, "成功", "module0: 数据预处理 已完成！")

    def on_error(self, err):
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"执行失败:\n{err}")
