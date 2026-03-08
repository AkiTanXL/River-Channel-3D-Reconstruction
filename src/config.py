"""
RC3DR 项目配置

提供项目配置管理，包括日志配置、路径配置等。
支持从外部文件加载配置（如JSON、YAML），提供默认配置和配置更新功能。
"""

import os
import json
from typing import Dict, Any, Optional


class RC3DRConfig:
    """
    RC3DR 配置管理器

    管理项目配置，支持：
    - 默认配置
    - 外部配置文件加载
    - 配置更新和保存
    - 环境变量覆盖
    """

    # 默认配置
    DEFAULT_CONFIG = {
        'logging': {
            'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'date_format': '%Y-%m-%d %H:%M:%S',
            'console': True,
            'file': True,
            'log_dir': '../logs',  # 从src目录向上到项目根目录
            'log_file': 'rc3dr_{date}.log',
            'max_file_size': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
            'encoding': 'utf-8',
            'module_levels': {
                # 模块特定日志级别配置
                # 示例：
                # 'rc3dr.module0': 'DEBUG',
                # 'rc3dr.utils': 'INFO',
            }
        },
        'paths': {
            'data_dir': '../data',
            'raw_data_dir': '../data/raw_data',
            'intermediate_data_dir': '../data/intermediate_data',
            'output_dir': '../data/output'
        },
        'processing': {
            'default_step_size': 2.0,
            'distance_threshold': 300.0,
            'interpolation_method': 'cubic_spline'  # cubic_spline, linear, pchip
        }
    }

    # 单例实例
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RC3DRConfig, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = self.DEFAULT_CONFIG.copy()
            self.config_file = None
            self._initialized = True

    def load_from_file(self, config_file: str):
        """
        从配置文件加载配置

        Args:
            config_file: 配置文件路径（支持JSON格式）
        """
        self.config_file = config_file

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            # 深度合并配置
            self._deep_update(self.config, file_config)
            return True
        except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
            # 如果文件不存在或格式错误，使用默认配置
            print(f"警告：无法加载配置文件 {config_file}，使用默认配置。错误：{e}")
            return False

    def save_to_file(self, config_file: Optional[str] = None):
        """
        保存当前配置到文件

        Args:
            config_file: 配置文件路径，如果为None则使用上次加载的文件
        """
        if config_file is None:
            config_file = self.config_file

        if config_file is None:
            print("错误：未指定配置文件路径")
            return False

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(config_file), exist_ok=True)

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            print(f"错误：无法保存配置文件 {config_file}。错误：{e}")
            return False

    def update(self, config: Dict[str, Any], merge: bool = True):
        """
        更新配置

        Args:
            config: 新的配置字典
            merge: 是否深度合并（True）或替换（False）
        """
        if merge:
            self._deep_update(self.config, config)
        else:
            self.config = config.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔，如 'logging.level'
            default: 默认值（如果键不存在）

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """
        设置配置值

        Args:
            key: 配置键，支持点号分隔，如 'logging.level'
            value: 配置值
        """
        keys = key.split('.')
        config = self.config

        # 遍历到最后一个键的父节点
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 设置值
        config[keys[-1]] = value

    def get_log_config(self) -> Dict[str, Any]:
        """
        获取日志配置

        Returns:
            日志配置字典
        """
        return self.config.get('logging', {})

    def update_log_config(self, log_config: Dict[str, Any]):
        """
        更新日志配置

        Args:
            log_config: 新的日志配置
        """
        if 'logging' not in self.config:
            self.config['logging'] = {}

        self._deep_update(self.config['logging'], log_config)

    def _deep_update(self, target: Dict, source: Dict):
        """
        深度合并字典

        Args:
            target: 目标字典（将被更新）
            source: 源字典（提供更新值）
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def resolve_path(self, path_key: str) -> str:
        """
        解析路径配置

        将相对路径（相对于项目根目录）转换为绝对路径。

        Args:
            path_key: 路径配置键，如 'paths.data_dir'

        Returns:
            绝对路径
        """
        path = self.get(path_key)
        if path is None:
            raise ValueError(f"路径配置键 '{path_key}' 不存在")

        if os.path.isabs(path):
            return path

        # 相对于项目根目录（src/的父目录）
        src_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(src_dir)
        return os.path.join(project_root, path)


# 全局配置实例
_config = RC3DRConfig()


def get_config() -> RC3DRConfig:
    """
    获取全局配置实例

    Returns:
        RC3DRConfig: 配置管理器实例
    """
    return _config


def load_config(config_file: str) -> bool:
    """
    从文件加载配置（便捷函数）

    Args:
        config_file: 配置文件路径

    Returns:
        是否成功加载
    """
    return _config.load_from_file(config_file)


def get_log_config() -> Dict[str, Any]:
    """
    获取日志配置（便捷函数）

    Returns:
        日志配置字典
    """
    return _config.get_log_config()


def update_log_config(log_config: Dict[str, Any]):
    """
    更新日志配置（便捷函数）

    Args:
        log_config: 新的日志配置
    """
    _config.update_log_config(log_config)


# 初始化：尝试从默认位置加载配置文件
def _init_config():
    """初始化配置，尝试从默认位置加载配置文件"""
    # 默认配置文件位置：项目根目录下的 config.json
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(src_dir)
    default_config_file = os.path.join(project_root, 'config.json')

    if os.path.exists(default_config_file):
        _config.load_from_file(default_config_file)


# 自动初始化
_init_config()