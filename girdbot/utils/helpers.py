"""
辅助函数 - 提供通用工具函数
"""
import time
import datetime
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Union, Dict, Optional, Tuple

def round_to_precision(value: Decimal, precision: Decimal, rounding=ROUND_DOWN) -> Decimal:
    """
    将数值舍入到指定精度
    
    Args:
        value: 要舍入的值
        precision: 精度值，如 0.01, 0.001 等
        rounding: 舍入方式，默认向下舍入
        
    Returns:
        舍入后的值
    """
    if precision == 0:
        return value
        
    return (value / precision).quantize(Decimal('1'), rounding=rounding) * precision

def safe_decimal(value, default=Decimal('0')) -> Decimal:
    """
    安全地将值转换为Decimal
    
    Args:
        value: 要转换的值
        default: 转换失败时的默认值
        
    Returns:
        转换后的Decimal值
    """
    if isinstance(value, Decimal):
        return value
        
    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            return Decimal(value)
        else:
            return default
    except:
        return default

def get_current_timestamp() -> float:
    """
    获取当前时间戳
    
    Returns:
        当前时间戳(秒)
    """
    return time.time()

def format_timestamp(timestamp: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳为可读字符串
    
    Args:
        timestamp: 时间戳(秒)
        fmt: 日期格式
        
    Returns:
        格式化后的日期时间字符串
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime(fmt)

def parse_timeframe(timeframe: str) -> int:
    """
    解析时间周期字符串为秒数
    
    Args:
        timeframe: 时间周期字符串，如 '1m', '5m', '1h', '1d'
        
    Returns:
        时间周期的秒数
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    
    if unit == 'm':
        return value * 60  # 分钟
    elif unit == 'h':
        return value * 60 * 60  # 小时
    elif unit == 'd':
        return value * 60 * 60 * 24  # 天
    elif unit == 'w':
        return value * 60 * 60 * 24 * 7  # 周
    else:
        raise ValueError(f"不支持的时间周期单位: {unit}")

def timeframe_to_seconds(timeframe: str) -> int:
    """
    将时间周期转换为秒数
    
    Args:
        timeframe: 时间周期字符串，如 '1m', '5m', '1h', '1d'
        
    Returns:
        时间周期的秒数
    """
    return parse_timeframe(timeframe)

def calculate_price_precision(market_info: Dict) -> Decimal:
    """
    根据市场信息计算价格精度
    
    Args:
        market_info: 市场信息字典
        
    Returns:
        价格精度
    """
    precision = market_info.get('precision', {}).get('price', 8)
    return Decimal(f"0.{'0' * (precision - 1)}1")

def calculate_amount_precision(market_info: Dict) -> Decimal:
    """
    根据市场信息计算数量精度
    
    Args:
        market_info: 市场信息字典
        
    Returns:
        数量精度
    """
    precision = market_info.get('precision', {}).get('amount', 8)
    return Decimal(f"0.{'0' * (precision - 1)}1")

def is_rate_limited(last_time: float, rate_limit: float) -> Tuple[bool, float]:
    """
    检查是否受到速率限制
    
    Args:
        last_time: 上次调用的时间戳
        rate_limit: 速率限制(秒)
        
    Returns:
        (是否受限, 需要等待的时间)
    """
    current_time = time.time()
    elapsed = current_time - last_time
    
    if elapsed < rate_limit:
        wait_time = rate_limit - elapsed
        return True, wait_time
    
    return False, 0

def truncate_string(text: str, max_length: int = 100) -> str:
    """
    截断字符串到指定长度
    
    Args:
        text: 原始字符串
        max_length: 最大长度
        
    Returns:
        可能被截断的字符串
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."

def format_number(value: Union[int, float, Decimal], decimals: int = 8) -> str:
    """
    格式化数字为固定小数位数的字符串
    
    Args:
        value: 数值
        decimals: 小数位数
        
    Returns:
        格式化后的字符串
    """
    format_str = f"{{:.{decimals}f}}"
    
    if isinstance(value, Decimal):
        # Decimal类型需要先转为字符串，避免科学计数法
        return format_str.format(float(value))
    else:
        return format_str.format(value)

def calculate_grid_prices(start_price: Decimal, end_price: Decimal, grid_levels: int) -> list:
    """
    计算网格价格点位
    
    Args:
        start_price: 起始价格
        end_price: 结束价格
        grid_levels: 网格级别数量
        
    Returns:
        价格点位列表
    """
    if grid_levels <= 1:
        return [start_price]
    
    # 计算价格步长
    price_range = end_price - start_price
    price_step = price_range / (grid_levels - 1)
    
    # 生成价格点位
    return [start_price + (price_step * i) for i in range(grid_levels)]

def get_environment_name() -> str:
    """
    获取当前环境名称
    
    Returns:
        环境名称: 'production', 'development' 或 'test'
    """
    return os.environ.get("ENVIRONMENT", "development")

def retry_async(max_retries: int = 3, delay: float = 1.0):
    """
    异步函数重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试延迟(秒)
    """
    import asyncio
    import functools
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        raise
                    
                    wait_time = delay * retries
                    logger.warning(f"{func.__name__} 失败，第 {retries} 次重试，等待 {wait_time} 秒: {e}")
                    await asyncio.sleep(wait_time)
        
        return wrapper
    
    return decorator

# 导入这里，避免循环引用
from girdbot.utils.logger import get_logger
logger = get_logger("helpers")