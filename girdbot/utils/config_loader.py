"""
配置加载器 - 负责加载和处理配置文件
"""
import os
import re
import yaml
from typing import Dict, Any, Optional

from girdbot.utils.logger import get_logger

logger = get_logger("config_loader")

def load_config(config_path: str) -> Optional[Dict[str, Any]]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典或None(加载失败时)
    """
    try:
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return None
            
        with open(config_path, 'r', encoding='utf-8') as file:
            # 加载YAML配置
            config = yaml.safe_load(file)
            
            # 处理环境变量
            config = _process_env_vars(config)
            
            logger.info(f"成功加载配置文件: {config_path}")
            return config
            
    except yaml.YAMLError as e:
        logger.error(f"解析YAML配置文件失败: {e}")
    except Exception as e:
        logger.error(f"加载配置文件时出错: {e}")
        
    return None

def _process_env_vars(config: Any) -> Any:
    """
    处理配置中的环境变量引用
    
    Args:
        config: 配置项(可能是字典、列表或标量值)
        
    Returns:
        处理后的配置
    """
    if isinstance(config, dict):
        return {k: _process_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_process_env_vars(item) for item in config]
    elif isinstance(config, str):
        # 处理环境变量引用，格式如 ${ENV_VAR} 或 ${ENV_VAR:default_value}
        pattern = r'\${([A-Za-z0-9_]+)(?::([^}]*))?}'
        
        def replace_env_var(match):
            env_var = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            
            return os.environ.get(env_var, default_value)
            
        return re.sub(pattern, replace_env_var, config)
    else:
        return config

def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    验证配置是否符合模式要求
    
    Args:
        config: 配置字典
        schema: 模式字典
        
    Returns:
        配置是否有效
    """
    # 简单的配置验证逻辑
    for key, schema_value in schema.items():
        # 检查必需项
        if schema_value.get("required", False) and key not in config:
            logger.error(f"缺少必需的配置项: {key}")
            return False
            
        # 如果配置中存在此项，则检查类型
        if key in config:
            value = config[key]
            expected_type = schema_value.get("type")
            
            if expected_type:
                # 处理类型检查
                if expected_type == "string" and not isinstance(value, str):
                    logger.error(f"配置项 {key} 应为字符串类型")
                    return False
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    logger.error(f"配置项 {key} 应为数字类型")
                    return False
                elif expected_type == "boolean" and not isinstance(value, bool):
                    logger.error(f"配置项 {key} 应为布尔类型")
                    return False
                elif expected_type == "array" and not isinstance(value, list):
                    logger.error(f"配置项 {key} 应为数组类型")
                    return False
                elif expected_type == "object" and not isinstance(value, dict):
                    logger.error(f"配置项 {key} 应为对象类型")
                    return False
    
    return True

def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并两个配置字典，后者的值会覆盖前者
    
    Args:
        base_config: 基础配置
        override_config: 覆盖配置
        
    Returns:
        合并后的配置
    """
    merged_config = base_config.copy()
    
    for key, value in override_config.items():
        # 如果两个配置都有该项，且都是字典，则递归合并
        if (key in merged_config and 
            isinstance(merged_config[key], dict) and 
            isinstance(value, dict)):
            merged_config[key] = merge_configs(merged_config[key], value)
        else:
            # 否则直接覆盖
            merged_config[key] = value
    
    return merged_config

def load_multiple_configs(config_paths: list) -> Optional[Dict[str, Any]]:
    """
    加载多个配置文件并合并
    
    Args:
        config_paths: 配置文件路径列表
        
    Returns:
        合并后的配置字典或None(加载失败时)
    """
    merged_config = {}
    
    for path in config_paths:
        config = load_config(path)
        if config:
            merged_config = merge_configs(merged_config, config)
        else:
            logger.warning(f"无法加载配置文件: {path}")
    
    return merged_config if merged_config else None

def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    通过路径获取配置值
    
    Args:
        config: 配置字典
        path: 配置路径，格式如 "system.log_level" 或 "exchanges[0].api_key"
        default: 默认值
        
    Returns:
        配置值或默认值
    """
    if not config:
        return default
        
    parts = path.split(".")
    current = config
    
    for part in parts:
        # 处理数组索引，如 exchanges[0]
        if "[" in part and part.endswith("]"):
            array_name = part[:part.index("[")]
            index_str = part[part.index("[")+1:part.index("]")]
            
            try:
                index = int(index_str)
                if array_name not in current or not isinstance(current[array_name], list):
                    return default
                    
                if index < 0 or index >= len(current[array_name]):
                    return default
                    
                current = current[array_name][index]
            except ValueError:
                return default
        else:
            # 普通属性
            if part not in current:
                return default
                
            current = current[part]
    
    return current