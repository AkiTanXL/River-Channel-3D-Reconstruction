"""
模块3：剖面点内插UI
"""

import sys
import os
import numpy as np
import geopandas as gpd
from PyQt5.QtWidgets import (QLabel, QLineEdit, QPushButton, QComboBox,
                              QHBoxLayout, QMessageBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
try:
    import module3_profile_interpolation as mod3
except ImportError as e:
    print(f"导入后端模块失败: {e}")

from base import BaseModuleUI
from components import WorkerThread


class Module3UI(BaseModuleUI):
    def __init__(self):
        super().__init__("模块3：剖面点内插")

        self.in_t_line = self.add_file_row(self.input_layout, 0, "深泓线 (.shp):",
                                           "../data/intermediate_data/深泓线.shp")
        self.in_t_interp = self.add_file_row(self.input_layout, 1, "深泓点内插 (.shp):",
                                             "../data/intermediate_data/深泓点内插.shp")
        self.in_l_interp = self.add_file_row(self.input_layout, 2, "左河岸点内插 (.shp):",
                                             "../data/intermediate_data/左河岸点内插.shp")
        self.in_r_interp = self.add_file_row(self.input_layout, 3, "右河岸点内插 (.shp):",
                                             "../data/intermediate_data/右河岸点内插.shp")
        self.in_prof = self.add_file_row(self.input_layout, 4, "剖面点 (.shp):", "../data/intermediate_data/剖面点.shp")

        self.out_prof_interp = self.add_file_row(self.output_layout, 0, "剖面点内插 (.shp):",
                                                 "../data/intermediate_data/剖面点内插.shp", False)

        self.param_layout.addWidget(QLabel("步长 (m):"), 0, 0)
        self.step_input = QLineEdit("2.0")
        self.param_layout.addWidget(self.step_input, 0, 1)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("选择内插剖面ID:"))
        self.combo_box = QComboBox()
        ctrl_layout.addWidget(self.combo_box)
        self.preview_layout.addLayout(ctrl_layout)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.preview_layout.addWidget(self.canvas)

        self.run_btn.clicked.connect(self.run_module)
        self.combo_box.currentTextChanged.connect(self.plot_preview)

        self.load_btn = QPushButton("加载数据并刷新预览视图")
        self.load_btn.clicked.connect(self.load_results)
        self.preview_layout.addWidget(self.load_btn)

        self.orig_prof_gdf = None

    def run_module(self):
        self.run_btn.setEnabled(False)
        step = float(self.step_input.text())
        self.thread = WorkerThread(
            mod3.run_profile_interpolation,
            self.in_t_line.text(), self.in_t_interp.text(),
            self.in_l_interp.text(), self.in_r_interp.text(),
            self.in_prof.text(), self.out_prof_interp.text(), step
        )
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()

    def on_finished(self):
        self.run_btn.setEnabled(True)
        self.load_results()
        QMessageBox.information(self, "成功", "module3: 剖面点内插 已完成！")

    def on_error(self, err):
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"执行失败:\n{err}")

    def load_results(self):
        try:
            self.interp_gdf = gpd.read_file(self.out_prof_interp.text())
            self.orig_prof_gdf = gpd.read_file(self.in_prof.text())

            prefixes = list(set([str(i)[:11] for i in self.interp_gdf['id']]))
            prefixes.sort()

            self.combo_box.blockSignals(True)
            self.combo_box.clear()
            self.combo_box.addItems(prefixes)
            self.combo_box.blockSignals(False)

            if prefixes:
                self.plot_preview(prefixes[0])
        except Exception as e:
            QMessageBox.warning(self, "警告", "无法读取内插结果或原始剖面数据，请确保文件存在。")

    def align_and_plot(self, ax, gdf, color, label, linestyle, marker, is_interp=False):
        if len(gdf) == 0: return

        coords = np.array([(geom.x, geom.y) for geom in gdf.geometry])
        diffs = np.diff(coords, axis=0)
        dists = np.linalg.norm(diffs, axis=1)
        cum_dist = np.insert(np.cumsum(dists), 0, 0)

        min_idx = gdf['z'].argmin()
        center_dist = cum_dist[min_idx]

        rel_dist = cum_dist - center_dist

        ax.plot(rel_dist, gdf['z'].values, color=color, linestyle=linestyle,
                marker=marker, label=label, linewidth=2 if is_interp else 1.5)

    def plot_preview(self, selected_id):
        if not selected_id or not hasattr(self, 'interp_gdf') or self.orig_prof_gdf is None:
            return

        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)

            parts = selected_id.split('_')
            if len(parts) >= 2:
                id1, id2 = parts[0], parts[1]
            else:
                return

            orig1 = self.orig_prof_gdf[self.orig_prof_gdf['id'].str.startswith(id1 + "_")].copy()
            orig2 = self.orig_prof_gdf[self.orig_prof_gdf['id'].str.startswith(id2 + "_")].copy()
            interp_prof = self.interp_gdf[self.interp_gdf['id'].str.startswith(selected_id + "_")].copy()

            self.align_and_plot(ax, orig1, 'blue', f'相邻实测剖面 {id1}', '--', '.', is_interp=False)
            self.align_and_plot(ax, orig2, 'purple', f'相邻实测剖面 {id2}', '-.', '.', is_interp=False)
            self.align_and_plot(ax, interp_prof, 'red', f'当前内插剖面 {selected_id}', '-', 'o', is_interp=True)

            ax.set_title("横断面高程对齐展示 (以深泓点为中心轴)")
            ax.set_xlabel("相对横向距离 (m)")
            ax.set_ylabel("高程 Z (m)")
            ax.axvline(x=0, color='gray', linestyle=':', alpha=0.7)

            ax.legend(loc='lower right', fontsize=10)
            ax.grid(True, linestyle='--')

            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "图表渲染失败", f"绘图时出现问题:\n{e}")
