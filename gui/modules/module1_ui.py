"""
模块1：深泓点内插UI
"""

import sys
import os
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QMessageBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
try:
    import module1_thalweg_interpolation as mod1
except ImportError as e:
    print(f"导入后端模块失败: {e}")

from base import BaseModuleUI
from components import WorkerThread


class Module1UI(BaseModuleUI):
    def __init__(self):
        super().__init__("模块1：深泓点内插")

        self.in_shore = self.add_file_row(self.input_layout, 0, "河岸线 (.shp):",
                                          "../data/intermediate_data/河岸线.shp")
        self.in_prof = self.add_file_row(self.input_layout, 1, "剖面点 (.shp):", "../data/intermediate_data/剖面点.shp")

        self.out_axis = self.add_file_row(self.output_layout, 0, "河道轴线 (.shp):",
                                          "../data/intermediate_data/河道轴线.shp", False)
        self.out_thalweg = self.add_file_row(self.output_layout, 1, "深泓线 (.shp):",
                                             "../data/intermediate_data/深泓线.shp", False)
        self.out_t_pts = self.add_file_row(self.output_layout, 2, "深泓点 (.shp):",
                                           "../data/intermediate_data/深泓点.shp", False)
        self.out_t_interp = self.add_file_row(self.output_layout, 3, "深泓点内插 (.shp):",
                                              "../data/intermediate_data/深泓点内插.shp", False)

        self.param_layout.addWidget(QLabel("步长 (m):"), 0, 0)
        self.step_input = QLineEdit("5.0")
        self.param_layout.addWidget(self.step_input, 0, 1)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.preview_layout.addWidget(self.canvas)

        self.run_btn.clicked.connect(self.run_module)
        self.preview_btn = QPushButton("加载数据并刷新预览视图")
        self.preview_btn.clicked.connect(self.plot_preview)
        self.preview_layout.addWidget(self.preview_btn)

    def run_module(self):
        self.run_btn.setEnabled(False)
        step = float(self.step_input.text())
        self.thread = WorkerThread(mod1.run_module1, step_length=step, base_dir=os.path.dirname(self.out_t_pts.text()))
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()

    def on_finished(self):
        self.run_btn.setEnabled(True)
        self.plot_preview()
        QMessageBox.information(self, "成功", "module1: 深泓点内插 已完成！")

    def on_error(self, err):
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"执行失败:\n{err}")

    def plot_preview(self):
        try:
            self.figure.clear()
            ax1 = self.figure.add_subplot(211)
            ax2 = self.figure.add_subplot(212)

            thalweg_line = gpd.read_file(self.out_thalweg.text())
            t_pts = gpd.read_file(self.out_t_pts.text())
            t_interp = gpd.read_file(self.out_t_interp.text())

            thalweg_line.plot(ax=ax1, color='blue', label='深泓线')
            t_pts.plot(ax=ax1, color='red', marker='o', markersize=30, label='深泓点')
            ax1.set_title("平面展示：深泓线与深泓点")
            ax1.set_xlabel("X (m)")
            ax1.set_ylabel("Y (m)")
            ax1.legend(loc='lower right', fontsize=10)

            if len(t_interp) > 1:
                interp_line_geom = LineString(t_interp.geometry.tolist())
                s_interp = [interp_line_geom.project(pt) for pt in t_interp.geometry]
                s_pts = [interp_line_geom.project(pt) for pt in t_pts.geometry]

                sort_idx = np.argsort(s_interp)
                s_interp = np.array(s_interp)[sort_idx]
                z_interp = t_interp['z'].values[sort_idx]
            else:
                s_interp, z_interp, s_pts = [], [], []

            ax2.plot(s_interp, z_interp, color='green', label='深泓点内插 (平滑曲线)')
            ax2.scatter(s_pts, t_pts['z'], color='red', label='深泓点 (已知点)', zorder=5)
            ax2.set_title("高程展示：拉直的深泓线高程剖面")
            ax2.set_xlabel("累积投影距离 (m)")
            ax2.set_ylabel("高程 Z (m)")
            ax2.legend(loc='lower right', fontsize=10)

            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "图表渲染失败", f"绘图时出现问题:\n{e}")
