"""
基础模块UI类
提供所有模块UI的通用框架和方法
"""

import os
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QGridLayout, QGroupBox, QLabel,
                              QLineEdit, QPushButton, QFileDialog)


class BaseModuleUI(QWidget):
    _project_root = None
    _config = None
    
    @classmethod
    def _find_project_root(cls):
        """查找项目根目录（包含data目录的父目录）"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):
            if os.path.isdir(os.path.join(current_dir, 'data')):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return None
    
    @classmethod
    def _load_path_config(cls):
        """加载路径配置文件"""
        if cls._project_root is None:
            return {}
        
        config_file = os.path.join(cls._project_root, 'gui_config.json')
        default_config = {
            'data_dir': 'data',
            'raw_data_dir': 'data/raw_data',
            'intermediate_data_dir': 'data/intermediate_data',
            'output_dir': 'data/output',
            'result_dir': 'data/result'
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                return {**default_config, **file_config}
            except Exception as e:
                print(f"警告：无法加载配置文件 {config_file}，使用默认配置。错误：{e}")
                return default_config
        
        return default_config
    
    def __init__(self, title):
        super().__init__()
        
        if BaseModuleUI._project_root is None:
            BaseModuleUI._project_root = self._find_project_root()
            BaseModuleUI._config = self._load_path_config()
        
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

    def get_data_path(self, relative_path):
        """
        解析数据路径，支持多种格式
        
        Args:
            relative_path: 相对路径或绝对路径
            - '../data/xxx': 转换为绝对路径
            - 绝对路径: 直接返回
            - 其他: 相对于项目根目录解析
            
        Returns:
            解析后的绝对路径
        """
        if BaseModuleUI._project_root is None:
            return relative_path
        
        if relative_path.startswith('../data/'):
            sub_path = relative_path.replace('../data/', '')
            return os.path.join(BaseModuleUI._project_root, 'data', sub_path)
        elif relative_path.startswith('../'):
            sub_path = relative_path.replace('../', '')
            return os.path.join(BaseModuleUI._project_root, sub_path)
        elif os.path.isabs(relative_path):
            return relative_path
        else:
            return os.path.join(BaseModuleUI._project_root, relative_path)

    def get_config_path(self, key):
        """
        从配置文件获取路径
        
        Args:
            key: 配置键名（如 'raw_data_dir', 'intermediate_data_dir'）
            
        Returns:
            解析后的绝对路径
        """
        if BaseModuleUI._config is None or key not in BaseModuleUI._config:
            return None
        
        relative_path = BaseModuleUI._config[key]
        return os.path.join(BaseModuleUI._project_root, relative_path)

    def add_file_row(self, layout, row, label_text, default_path, is_input=True):
        """
        添加文件路径输入行
        
        Args:
            layout: 布局对象
            row: 行号
            label_text: 标签文本
            default_path: 默认路径（支持相对路径）
            is_input: 是否为输入文件
            
        Returns:
            QLineEdit对象
        """
        layout.addWidget(QLabel(label_text), row, 0)
        resolved_path = self.get_data_path(default_path)
        line_edit = QLineEdit(resolved_path)
        layout.addWidget(line_edit, row, 1)
        btn = QPushButton("浏览")
        btn.clicked.connect(lambda: self.browse_file(line_edit, is_input))
        layout.addWidget(btn, row, 2)
        return line_edit

    def browse_file(self, line_edit, is_input):
        """文件浏览对话框"""
        path, _ = QFileDialog.getOpenFileName() if is_input else QFileDialog.getSaveFileName()
        if path:
            line_edit.setText(path)
