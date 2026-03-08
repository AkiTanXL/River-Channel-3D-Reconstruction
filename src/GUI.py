import sys
import os
import logging
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel,
                             QLineEdit, QPushButton, QTextBrowser, QStackedWidget,
                             QAction, QFileDialog, QTabWidget, QComboBox, QMessageBox)
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 解决Matplotlib中文显示问题
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 导入后端模块
try:
    import module0_data_preprocessing as mod0
    import module1_thalweg_interpolation as mod1
    import module2_bank_interpolation as mod2
    import module3_profile_interpolation as mod3
except ImportError as e:
    print(f"导入后端模块失败，请确保本脚本与后端脚本在同一目录: {e}")


# ==========================================
# 1. 线程安全的日志重定向类
# ==========================================
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


# ==========================================
# 2. 异步工作线程
# ==========================================
class WorkerThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.target_func(*self.args, **self.kwargs)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ==========================================
# 3. 基础模块 UI 类
# ==========================================
class BaseModuleUI(QWidget):
    def __init__(self, title):
        super().__init__()
        self.layout = QHBoxLayout(self)

        self.left_layout = QVBoxLayout()
        self.input_group = QGroupBox("数据输入")
        self.input_layout = QGridLayout()
        self.input_group.setLayout(self.input_layout)

        self.output_group = QGroupBox("数据输出")
        self.output_layout = QGridLayout()
        self.output_group.setLayout(self.output_layout)

        self.param_group = QGroupBox("参数设置")
        self.param_layout = QGridLayout()
        self.param_group.setLayout(self.param_layout)

        self.run_btn = QPushButton("执行处理")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

        self.left_layout.addWidget(self.input_group)
        self.left_layout.addWidget(self.output_group)
        self.left_layout.addWidget(self.param_group)
        self.left_layout.addWidget(self.run_btn)
        self.left_layout.addStretch()

        self.preview_group = QGroupBox("成果预览")
        self.preview_layout = QVBoxLayout()
        self.preview_group.setLayout(self.preview_layout)

        self.layout.addLayout(self.left_layout, 1)
        self.layout.addWidget(self.preview_group, 2)

    def add_file_row(self, layout, row, label_text, default_path, is_input=True):
        layout.addWidget(QLabel(label_text), row, 0)
        line_edit = QLineEdit(default_path)
        layout.addWidget(line_edit, row, 1)
        btn = QPushButton("浏览")
        btn.clicked.connect(lambda: self.browse_file(line_edit, is_input))
        layout.addWidget(btn, row, 2)
        return line_edit

    def browse_file(self, line_edit, is_input):
        path, _ = QFileDialog.getOpenFileName() if is_input else QFileDialog.getSaveFileName()
        if path:
            line_edit.setText(path)


# ==========================================
# 4. 各模块具体 UI 实现
# ==========================================
class Module0UI(BaseModuleUI):
    def __init__(self):
        super().__init__("模块0：数据预处理")

        self.preview_group.hide()

        # ================= 输入 =================
        self.in_shore = self.add_file_row(self.input_layout, 0, "河岸线 (.shp):", "../data/raw_data/河岸线.shp")
        self.in_bank = self.add_file_row(self.input_layout, 1, "实测河岸点 (.shp):", "../data/raw_data/实测河岸点.shp")
        self.in_prof = self.add_file_row(self.input_layout, 2, "剖面点 (.shp):", "../data/raw_data/剖面点.shp")

        # ================= 输出 =================
        self.out_shore = self.add_file_row(self.output_layout, 0, "河岸线 (.shp):",
                                           "../data/intermediate_data/河岸线.shp", False)
        self.out_lbank = self.add_file_row(self.output_layout, 1, "左河岸点 (.shp):",
                                           "../data/intermediate_data/左河岸点.shp", False)
        self.out_rbank = self.add_file_row(self.output_layout, 2, "右河岸点 (.shp):",
                                           "../data/intermediate_data/右河岸点.shp", False)
        self.out_prof = self.add_file_row(self.output_layout, 3, "剖面点 (.shp):",
                                          "../data/intermediate_data/剖面点.shp", False)

        # ================= 参数设置 =================

        # 按钮：读取字段
        self.load_fields_btn = QPushButton("读取字段")
        self.load_fields_btn.clicked.connect(self.load_fields)
        self.param_layout.addWidget(self.load_fields_btn, 0, 0, 1, 2)

        # 河岸点字段
        self.param_layout.addWidget(QLabel("河岸点 X 字段:"), 1, 0)
        self.bank_x = QComboBox()
        self.param_layout.addWidget(self.bank_x, 1, 1)

        self.param_layout.addWidget(QLabel("河岸点 Y 字段:"), 2, 0)
        self.bank_y = QComboBox()
        self.param_layout.addWidget(self.bank_y, 2, 1)

        self.param_layout.addWidget(QLabel("河岸点 Z 字段:"), 3, 0)
        self.bank_z = QComboBox()
        self.param_layout.addWidget(self.bank_z, 3, 1)

        # 剖面点字段
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

    # =====================================
    # 自动读取字段
    # =====================================
    def load_fields(self):
        try:
            bank_file = self.in_bank.text()
            prof_file = self.in_prof.text()

            bank_gdf = gpd.read_file(bank_file)
            prof_gdf = gpd.read_file(prof_file)

            bank_fields = list(bank_gdf.columns)
            prof_fields = list(prof_gdf.columns)

            # 清空
            self.bank_x.clear()
            self.bank_y.clear()
            self.bank_z.clear()

            self.prof_x.clear()
            self.prof_y.clear()
            self.prof_z.clear()
            self.prof_id.clear()

            # 添加字段
            self.bank_x.addItems(bank_fields)
            self.bank_y.addItems(bank_fields)
            self.bank_z.addItems(bank_fields)

            self.prof_x.addItems(prof_fields)
            self.prof_y.addItems(prof_fields)
            self.prof_z.addItems(prof_fields)
            self.prof_id.addItems(prof_fields)

            # 自动选择推荐字段
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

    # 自动匹配字段
    def auto_select_field(self, combo, candidates):
        for name in candidates:
            idx = combo.findText(name)
            if idx != -1:
                combo.setCurrentIndex(idx)
                return

    # =====================================
    # 执行模块
    # =====================================
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

            # 平面绘制
            thalweg_line.plot(ax=ax1, color='blue', label='深泓线')
            t_pts.plot(ax=ax1, color='red', marker='o', markersize=30, label='深泓点')
            ax1.set_title("平面展示：深泓线与深泓点")
            ax1.set_xlabel("X (m)")
            ax1.set_ylabel("Y (m)")
            ax1.legend(loc='lower right', fontsize=10)

            # 高程投影计算
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

            # ================= 1. 计算全局统一边界，防止跳动 =================
            # 1.1 平面全局范围 (X, Y)
            minx, miny, maxx, maxy = bank_lines.total_bounds
            pad_x = (maxx - minx) * 0.05
            pad_y = (maxy - miny) * 0.05
            xlims_plan = (minx - pad_x, maxx + pad_x)
            ylims_plan = (miny - pad_y, maxy + pad_y)

            # 1.2 高程全局范围 (Z)
            all_z = np.concatenate([l_pts['z'].values, r_pts['z'].values])
            min_z, max_z = all_z.min(), all_z.max()
            pad_z = (max_z - min_z) * 0.1 if max_z > min_z else 1.0
            zlims = (min_z - pad_z, max_z + pad_z)

            # 1.3 投影距离全局范围 (S)
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

            # ================= 2. 绘制左岸 =================
            self.fig_l.clear()
            # 【修复跳变核心】放弃动态 tight_layout，强制固定边距百分比，确保绘图框(BoundingBox)大小绝对一致
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

            # ================= 3. 绘制右岸 =================
            self.fig_r.clear()
            # 同理，强制右侧图表的布局边距与左侧完全一样
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

        self.orig_prof_gdf = None  # 用于缓存原始实测剖面

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

            # 提取所有类似于 001_002_003 的前缀
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

        # 为了保证曲线顺滑，确保点按照空间距离排序
        coords = np.array([(geom.x, geom.y) for geom in gdf.geometry])
        diffs = np.diff(coords, axis=0)
        dists = np.linalg.norm(diffs, axis=1)
        cum_dist = np.insert(np.cumsum(dists), 0, 0)

        # 寻找深泓点作为对齐轴线（Z值最小点）
        min_idx = gdf['z'].argmin()
        center_dist = cum_dist[min_idx]

        # 计算相对横向距离（深泓点处距离为0，左侧为负，右侧为正）
        rel_dist = cum_dist - center_dist

        ax.plot(rel_dist, gdf['z'].values, color=color, linestyle=linestyle,
                marker=marker, label=label, linewidth=2 if is_interp else 1.5)

    def plot_preview(self, selected_id):
        if not selected_id or not hasattr(self, 'interp_gdf') or self.orig_prof_gdf is None:
            return

        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)

            # 解析 ID，例如 '001_002_003' -> '001' 和 '002'
            parts = selected_id.split('_')
            if len(parts) >= 2:
                id1, id2 = parts[0], parts[1]
            else:
                return

            # 筛选对应的三个剖面数据
            orig1 = self.orig_prof_gdf[self.orig_prof_gdf['id'].str.startswith(id1 + "_")].copy()
            orig2 = self.orig_prof_gdf[self.orig_prof_gdf['id'].str.startswith(id2 + "_")].copy()
            interp_prof = self.interp_gdf[self.interp_gdf['id'].str.startswith(selected_id + "_")].copy()

            # 以深泓点为中心对齐绘制实测和内插剖面
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


# ==========================================
# 5. 主窗口定义
# ==========================================
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

        # ------------------ 堆叠窗口 ------------------
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

        # ------------------ 日志窗口 ------------------
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


# ==========================================
# 6. 应用程序入口
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())