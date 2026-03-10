"""
模块2：河岸点内插UI
"""

import sys
import os
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from PyQt5.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton,
                              QTabWidget, QVBoxLayout, QHBoxLayout, QMessageBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
try:
    import module2_bank_interpolation as mod2
except ImportError as e:
    print(f"导入后端模块失败: {e}")

from base import BaseModuleUI
from components import WorkerThread


class Module2UI(BaseModuleUI):
    def __init__(self):
        super().__init__("模块2：河岸点内插")

        self.in_shore = self.add_file_row(self.input_layout, 0, "河岸线 (.shp):",
                                          "../data/intermediate_data/河岸线.shp")
        self.in_t_line = self.add_file_row(self.input_layout, 1, "深泓线 (.shp):",
                                           "../data/intermediate_data/深泓线.shp")
        self.in_t_interp = self.add_file_row(self.input_layout, 2, "深泓点内插 (.shp):",
                                             "../data/intermediate_data/深泓点内插.shp")
        self.in_lbank = self.add_file_row(self.input_layout, 3, "左河岸点 (.shp):",
                                          "../data/intermediate_data/左河岸点.shp")
        self.in_rbank = self.add_file_row(self.input_layout, 4, "右河岸点 (.shp):",
                                          "../data/intermediate_data/右河岸点.shp")

        self.out_l_interp = self.add_file_row(self.output_layout, 0, "左河岸点内插 (.shp):",
                                              "../data/intermediate_data/左河岸点内插.shp", False)
        self.out_r_interp = self.add_file_row(self.output_layout, 1, "右河岸点内插 (.shp):",
                                              "../data/intermediate_data/右河岸点内插.shp", False)

        self.param_layout.addWidget(QLabel("阈值 (m):"), 0, 0)
        self.thresh_input = QLineEdit("300.0")
        self.param_layout.addWidget(self.thresh_input, 0, 1)

        self.tabs = QTabWidget()
        self.left_tab = QWidget()
        self.right_tab = QWidget()
        self.tabs.addTab(self.left_tab, "左河岸预览")
        self.tabs.addTab(self.right_tab, "右河岸预览")
        self.preview_layout.addWidget(self.tabs)

        self.fig_l = Figure()
        self.canvas_l = FigureCanvas(self.fig_l)
        QVBoxLayout(self.left_tab).addWidget(self.canvas_l)

        self.fig_r = Figure()
        self.canvas_r = FigureCanvas(self.fig_r)
        QVBoxLayout(self.right_tab).addWidget(self.canvas_r)

        self.run_btn.clicked.connect(self.run_module)
        self.preview_btn = QPushButton("加载数据并刷新预览视图")
        self.preview_btn.clicked.connect(self.plot_preview)
        self.preview_layout.addWidget(self.preview_btn)

    def run_module(self):
        self.run_btn.setEnabled(False)
        thresh = float(self.thresh_input.text())
        self.thread = WorkerThread(
            mod2.process_bank_interpolation,
            self.in_t_line.text(), self.in_t_interp.text(), self.in_shore.text(),
            self.in_lbank.text(), self.in_rbank.text(),
            self.out_l_interp.text(), self.out_r_interp.text(), thresh
        )
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()

    def on_finished(self):
        self.run_btn.setEnabled(True)
        self.plot_preview()
        QMessageBox.information(self, "成功", "module2: 河岸点内插 已完成！")

    def on_error(self, err):
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"执行失败:\n{err}")

    def plot_preview(self):
        try:
            bank_lines = gpd.read_file(self.in_shore.text())
            l_pts = gpd.read_file(self.in_lbank.text())
            r_pts = gpd.read_file(self.in_rbank.text())
            l_interp = gpd.read_file(self.out_l_interp.text())
            r_interp = gpd.read_file(self.out_r_interp.text())

            minx, miny, maxx, maxy = bank_lines.total_bounds
            pad_x = (maxx - minx) * 0.05
            pad_y = (maxy - miny) * 0.05
            xlims_plan = (minx - pad_x, maxx + pad_x)
            ylims_plan = (miny - pad_y, maxy + pad_y)

            all_z = np.concatenate([l_pts['z'].values, r_pts['z'].values])
            min_z, max_z = all_z.min(), all_z.max()
            pad_z = (max_z - min_z) * 0.1 if max_z > min_z else 1.0
            zlims = (min_z - pad_z, max_z + pad_z)

            max_s = 0.0
            s_l_interp, s_l_pts = [], []
            if len(l_interp) > 1:
                l_line_geom = LineString(l_interp.geometry.tolist())
                max_s = max(max_s, l_line_geom.length)
                s_l_interp = [l_line_geom.project(pt) for pt in l_interp.geometry]
                s_l_pts = [l_line_geom.project(pt) for pt in l_pts.geometry]

            s_r_interp, s_r_pts = [], []
            if len(r_interp) > 1:
                r_line_geom = LineString(r_interp.geometry.tolist())
                max_s = max(max_s, r_line_geom.length)
                s_r_interp = [r_line_geom.project(pt) for pt in r_interp.geometry]
                s_r_pts = [r_line_geom.project(pt) for pt in r_pts.geometry]

            xlims_s = (-max_s * 0.02, max_s * 1.02) if max_s > 0 else (0, 1)

            self.fig_l.clear()
            self.fig_l.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1, hspace=0.35)

            ax1 = self.fig_l.add_subplot(211)
            ax2 = self.fig_l.add_subplot(212)

            bank_lines[bank_lines['id'] == 0].plot(ax=ax1, color='blue', label='左河岸线')
            l_pts.plot(ax=ax1, color='red', markersize=30, label='左河岸点')
            ax1.set_title("平面：左岸")
            ax1.set_xlim(xlims_plan)
            ax1.set_ylim(ylims_plan)
            ax1.legend(loc='lower right', fontsize=10)

            if len(s_l_interp) > 0:
                sort_idx = np.argsort(s_l_interp)
                ax2.plot(np.array(s_l_interp)[sort_idx], l_interp['z'].values[sort_idx], color='green',
                         label='内插点高程')
                ax2.scatter(s_l_pts, l_pts['z'], color='red', label='左河岸点 (已知)', zorder=5)

            ax2.set_title("高程：左岸拉直")
            ax2.set_xlim(xlims_s)
            ax2.set_ylim(zlims)
            ax2.legend(loc='lower right', fontsize=10)

            self.canvas_l.draw()

            self.fig_r.clear()
            self.fig_r.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1, hspace=0.35)

            ax3 = self.fig_r.add_subplot(211)
            ax4 = self.fig_r.add_subplot(212)

            bank_lines[bank_lines['id'] == 1].plot(ax=ax3, color='blue', label='右河岸线')
            r_pts.plot(ax=ax3, color='red', markersize=30, label='右河岸点')
            ax3.set_title("平面：右岸")
            ax3.set_xlim(xlims_plan)
            ax3.set_ylim(ylims_plan)
            ax3.legend(loc='lower right', fontsize=10)

            if len(s_r_interp) > 0:
                sort_idx = np.argsort(s_r_interp)
                ax4.plot(np.array(s_r_interp)[sort_idx], r_interp['z'].values[sort_idx], color='green',
                         label='内插点高程')
                ax4.scatter(s_r_pts, r_pts['z'], color='red', label='右河岸点 (已知)', zorder=5)

            ax4.set_title("高程：右岸拉直")
            ax4.set_xlim(xlims_s)
            ax4.set_ylim(zlims)
            ax4.legend(loc='lower right', fontsize=10)

            self.canvas_r.draw()

        except Exception as e:
            QMessageBox.warning(self, "图表渲染失败", f"绘图时出现问题:\n{e}")
