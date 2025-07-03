"""
日志配置 - 配置项目日志记录
"""
import os
import sys
import logging
import logging.handlers
from typing import Optional

import colorlog

# 全局日志记录器字典
_loggers = {}

def setup_logger(name: str = "girdbot", level: str = None, log_file: str = None) -> logging.Logger:
    """
    设置并配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别，默认从环境变量或INFO
        log_file: 日志文件路径，默认None(不写入文件)
        
    Returns:
        配置好的日志记录器
    """
    global _loggers
    
    # 如果已经存在此记录器，则直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 确定日志级别
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
        
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    logger.propagate = False  # 防止日志被传递到根日志记录器
    
    # 如果记录器已有处理器，则清空
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # 设置控制台彩色日志格式
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        },
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，则添加文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建文件处理器(支持日志轮转)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        
        # 设置文件日志格式
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # 保存记录器引用
    _loggers[name] = logger
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器
    """
    global _loggers
    
    # 如果记录器不存在，则创建
    if name not in _loggers:
        _loggers[name] = setup_logger(name)
    
    return _loggers[name]

def set_log_level(level: str, logger_name: Optional[str] = None):
    """
    设置日志级别
    
    Args:
        level: 日志级别
        logger_name: 日志记录器名称，默认为None(所有记录器)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    if logger_name:
        # 设置指定记录器的级别
        logger = get_logger(logger_name)
        logger.setLevel(numeric_level)
        
        # 同时设置该记录器的所有处理器
        for handler in logger.handlers:
            handler.setLevel(numeric_level)
    else:
        # 设置所有记录器的级别
        for name, logger in _loggers.items():
            logger.setLevel(numeric_level)
            
            # 同时设置所有处理器
            for handler in logger.handlers:
                handler.setLevel(numeric_level)

def setup_file_logging(log_dir: str = "./logs"):
    """
    为所有已存在的记录器设置文件日志
    
    Args:
        log_dir: 日志目录
    """
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 为所有记录器添加文件处理器
    for name, logger in _loggers.items():
        log_file = os.path.join(log_dir, f"{name}.log")
        
        # 检查记录器是否已有文件处理器
        has_file_handler = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        if has_file_handler:
            continue
            
        # 创建文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logger.level)
        
        # 设置文件日志格式
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)