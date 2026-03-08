"""
RC3DR 统一日志系统

提供统一的日志配置和管理接口，支持控制台和文件输出，日志轮转，模块化日志记录。
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Optional, Dict, Any


class RC3DRLogger:
    """
    RC3DR 日志管理器

    管理整个项目的日志配置，支持：
    - 统一日志格式和级别配置
    - 控制台和文件输出
    - 日志轮转（按大小和备份数量）
    - 模块化日志记录
    - 回退机制
    """

    # 默认配置
    DEFAULT_CONFIG = {
        'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'date_format': '%Y-%m-%d %H:%M:%S',
        'console': True,
        'file': True,
        'log_dir': '../logs',  # 从src目录向上到项目根目录
        'log_file': 'rc3dr_{date}.log',
        'max_file_size': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5,
        'encoding': 'utf-8'
    }

    # 单例实例
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RC3DRLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config = self.DEFAULT_CONFIG.copy()
            self._root_logger = None
            self._handlers = {}
            self._module_levels = {}
            RC3DRLogger._initialized = True

    def configure(self, config: Optional[Dict[str, Any]] = None):
        """
        配置日志系统

        Args:
            config: 配置字典，覆盖默认配置
        """
        if config:
            self.config.update(config)

        # 确保日志目录存在
        log_dir = self.config['log_dir']
        if not os.path.isabs(log_dir):
            # 相对于当前文件所在目录（src/）
            src_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(src_dir, log_dir)

        os.makedirs(log_dir, exist_ok=True)
        self.config['log_dir'] = log_dir

    def setup(self):
        """
        设置根日志记录器

        配置控制台和文件处理器，应用默认格式。
        如果已经设置过，则跳过。
        """
        if self._root_logger is not None:
            return

        root_logger = logging.getLogger('rc3dr')
        root_logger.setLevel(getattr(logging, self.config['level']))

        # 移除可能存在的现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 创建格式化器
        formatter = logging.Formatter(
            fmt=self.config['format'],
            datefmt=self.config['date_format']
        )

        # 控制台处理器
        if self.config['console']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(getattr(logging, self.config['level']))
            root_logger.addHandler(console_handler)
            self._handlers['console'] = console_handler

        # 文件处理器（带轮转）
        if self.config['file']:
            # 生成日志文件名
            date_str = datetime.now().strftime('%Y%m%d')
            log_filename = self.config['log_file'].format(date=date_str)
            log_path = os.path.join(self.config['log_dir'], log_filename)

            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=log_path,
                    maxBytes=self.config['max_file_size'],
                    backupCount=self.config['backup_count'],
                    encoding=self.config['encoding']
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(getattr(logging, self.config['level']))
                root_logger.addHandler(file_handler)
                self._handlers['file'] = file_handler
            except (OSError, IOError) as e:
                # 文件权限问题，回退到只使用控制台输出
                print(f"警告：无法创建日志文件 {log_path}，错误：{e}。将仅使用控制台输出。")

        # 防止日志传递给父记录器
        root_logger.propagate = False
        self._root_logger = root_logger

        # 记录初始化信息
        root_logger.info(f"RC3DR日志系统初始化完成，日志级别：{self.config['level']}")
        if self.config['file'] and 'file' in self._handlers:
            root_logger.info(f"日志文件：{log_path}")

    def get_logger(self, name: str = 'rc3dr') -> logging.Logger:
        """
        获取指定名称的日志记录器

        Args:
            name: 记录器名称，默认 'rc3dr'

        Returns:
            logging.Logger: 配置好的日志记录器
        """
        # 确保根记录器已设置
        if self._root_logger is None:
            self.setup()

        # 获取或创建记录器
        logger = logging.getLogger(name)

        # 如果指定了模块特定级别，则应用
        if name in self._module_levels:
            logger.setLevel(getattr(logging, self._module_levels[name]))

        return logger

    def get_module_logger(self, module_name: str) -> logging.Logger:
        """
        获取模块专用日志记录器

        记录器名称格式为 'rc3dr.{module_name}'，便于按模块过滤日志。

        Args:
            module_name: 模块名称，如 'module0'、'utils' 等

        Returns:
            logging.Logger: 模块专用日志记录器
        """
        logger_name = f"rc3dr.{module_name}"
        return self.get_logger(logger_name)

    def set_module_level(self, module_name: str, level: str):
        """
        设置模块特定日志级别

        Args:
            module_name: 模块名称
            level: 日志级别，如 'DEBUG'、'INFO'、'WARNING'、'ERROR'、'CRITICAL'
        """
        logger_name = f"rc3dr.{module_name}"
        self._module_levels[logger_name] = level

        # 如果记录器已存在，立即更新其级别
        if logger_name in logging.Logger.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.setLevel(getattr(logging, level))

    def update_config(self, config: Dict[str, Any]):
        """
        更新配置并重新设置日志系统

        Args:
            config: 新的配置字典
        """
        self.configure(config)

        # 重新设置日志系统
        self._root_logger = None
        self._handlers.clear()
        self.setup()


# 全局日志管理器实例
_logger_manager = RC3DRLogger()


def setup_default_logging(config: Optional[Dict[str, Any]] = None):
    """
    设置默认日志配置（便捷函数）

    Args:
        config: 可选的配置字典
    """
    _logger_manager.configure(config)
    _logger_manager.setup()


def get_logger(name: str = 'rc3dr') -> logging.Logger:
    """
    获取指定名称的日志记录器（便捷函数）

    Args:
        name: 记录器名称

    Returns:
        logging.Logger: 日志记录器
    """
    return _logger_manager.get_logger(name)


def get_module_logger(module_name: str) -> logging.Logger:
    """
    获取模块专用日志记录器（便捷函数）

    Args:
        module_name: 模块名称

    Returns:
        logging.Logger: 模块专用日志记录器
    """
    return _logger_manager.get_module_logger(module_name)


def log_exception(logger: logging.Logger, exception: Exception,
                  message: str = "发生异常", level: str = 'ERROR'):
    """
    统一记录异常信息

    Args:
        logger: 日志记录器
        exception: 异常对象
        message: 自定义消息
        level: 日志级别
    """
    log_method = getattr(logger, level.lower(), logger.error)
    log_method(f"{message}: {type(exception).__name__}: {str(exception)}")


def log_progress(logger: logging.Logger, current: int, total: int,
                 message: str = "进度"):
    """
    记录进度信息

    Args:
        logger: 日志记录器
        current: 当前进度
        total: 总进度
        message: 进度描述
    """
    if total > 0:
        percentage = (current / total) * 100
        logger.info(f"{message}: {current}/{total} ({percentage:.1f}%)")
    else:
        logger.info(f"{message}: {current}")


# 回退机制：如果无法导入此模块，提供简单logging配置
def _setup_fallback_logging():
    """设置回退日志配置（当logger.py无法正常导入时使用）"""
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.getLogger().info("使用回退日志配置")
    except Exception:
        # 如果连basicConfig都失败，至少确保程序能运行
        pass


# 自动设置默认配置
try:
    setup_default_logging()
except Exception as e:
    print(f"警告：RC3DR日志系统初始化失败，使用回退配置。错误：{e}")
    _setup_fallback_logging()