"""
交易所基类 - 定义通用交易所接口
"""
import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any

class ExchangeBase(ABC):
    """交易所基类，定义所有交易所共有的接口方法"""
    
    def __init__(self, api_key: str, api_secret: str, name: str, account_alias: str = None):
        """
        初始化交易所基类
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            name: 交易所名称
            account_alias: 账户别名(可选)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = name
        self.id = f"{name}_{account_alias}" if account_alias else name
        self.account_alias = account_alias
        self.initialized = False
        self.markets = {}
        self.trading_rules = {}
        self.symbols = []
    
    @abstractmethod
    async def initialize(self):
        """
        初始化交易所连接
        """
        pass
    
    @abstractmethod
    async def close(self):
        """
        关闭交易所连接
        """
        pass
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对的行情数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含行情数据的字典
        """
        pass
    
    @abstractmethod
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        获取账户余额
        
        Returns:
            包含余额数据的字典
        """
        pass
    
    @abstractmethod
    async def fetch_market_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对市场信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含市场信息的字典
        """
        pass
    
    @abstractmethod
    async def create_limit_order(self, symbol: str, side: str, amount: Decimal, price: Decimal) -> str:
        """
        创建限价单
        
        Args:
            symbol: 交易对符号
            side: 交易方向，'buy' 或 'sell'
            amount: 交易数量
            price: 交易价格
            
        Returns:
            订单ID
        """
        pass
    
    @abstractmethod
    async def create_market_order(self, symbol: str, side: str, amount: Decimal) -> str:
        """
        创建市价单
        
        Args:
            symbol: 交易对符号
            side: 交易方向，'buy' 或 'sell'
            amount: 交易数量
            
        Returns:
            订单ID
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            是否成功取消
        """
        pass
    
    @abstractmethod
    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            包含订单信息的字典
        """
        pass
    
    @abstractmethod
    async def fetch_orders(self, symbol: str = None, since: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取订单列表
        
        Args:
            symbol: 交易对符号(可选)
            since: 起始时间戳(可选)
            limit: 返回数量限制(可选)
            
        Returns:
            订单列表
        """
        pass
    
    @abstractmethod
    async def fetch_orders_by_ids(self, order_ids: List[str], symbol: str = None) -> Dict[str, Dict[str, Any]]:
        """
        批量获取订单信息
        
        Args:
            order_ids: 订单ID列表
            symbol: 交易对符号(可选)
            
        Returns:
            订单ID -> 订单信息的字典
        """
        pass
    
    @abstractmethod
    async def fetch_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对符号(可选)
            
        Returns:
            持仓列表
        """
        pass
    
    async def ping(self) -> bool:
        """
        测试连接
        
        Returns:
            连接是否正常
        """
        try:
            await self.fetch_ticker("BTC/USDT")
            return True
        except Exception:
            return False
    
    def is_active(self) -> bool:
        """
        检查连接是否已初始化并活跃
        
        Returns:
            是否活跃
        """
        return self.initialized
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', since: int = None, limit: int = None) -> List[List[float]]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期，如 '1m', '5m', '1h', '1d'
            since: 起始时间戳(可选)
            limit: 返回数量限制(可选)
            
        Returns:
            K线数据列表 [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量]
        """
        raise NotImplementedError("fetch_ohlcv方法未实现")
    
    async def fetch_order_book(self, symbol: str, limit: int = None) -> Dict[str, Any]:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对符号
            limit: 深度限制(可选)
            
        Returns:
            包含订单簿数据的字典
        """
        raise NotImplementedError("fetch_order_book方法未实现")
    
    async def fetch_trades(self, symbol: str, since: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取最近成交
        
        Args:
            symbol: 交易对符号
            since: 起始时间戳(可选)
            limit: 返回数量限制(可选)
            
        Returns:
            成交列表
        """
        raise NotImplementedError("fetch_trades方法未实现")
    
    async def create_order(self, symbol: str, order_type: str, side: str, amount: Decimal, price: Decimal = None, params: Dict = None) -> Dict[str, Any]:
        """
        创建订单（通用方法）
        
        Args:
            symbol: 交易对符号
            order_type: 订单类型，如 'limit', 'market'
            side: 交易方向，'buy' 或 'sell'
            amount: 交易数量
            price: 交易价格(可选，市价单不需要)
            params: 额外参数(可选)
            
        Returns:
            订单信息
        """
        if order_type == 'limit':
            if price is None:
                raise ValueError("限价单必须指定价格")
            return await self.create_limit_order(symbol, side, amount, price)
        elif order_type == 'market':
            return await self.create_market_order(symbol, side, amount)
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")
    
    async def fetch_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        获取未成交订单
        
        Args:
            symbol: 交易对符号(可选)
            
        Returns:
            未成交订单列表
        """
        raise NotImplementedError("fetch_open_orders方法未实现")
    
    async def fetch_closed_orders(self, symbol: str = None, since: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取已成交订单
        
        Args:
            symbol: 交易对符号(可选)
            since: 起始时间戳(可选)
            limit: 返回数量限制(可选)
            
        Returns:
            已成交订单列表
        """
        raise NotImplementedError("fetch_closed_orders方法未实现")
    
    async def cancel_all_orders(self, symbol: str = None) -> bool:
        """
        取消所有订单
        
        Args:
            symbol: 交易对符号(可选)
            
        Returns:
            是否成功取消
        """
        raise NotImplementedError("cancel_all_orders方法未实现")
    
    async def fetch_my_trades(self, symbol: str = None, since: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取自己的成交历史
        
        Args:
            symbol: 交易对符号(可选)
            since: 起始时间戳(可选)
            limit: 返回数量限制(可选)
            
        Returns:
            成交历史列表
        """
        raise NotImplementedError("fetch_my_trades方法未实现")
    
    def get_market_info(self, symbol: str) -> Dict[str, Any]:
        """
        从缓存获取市场信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            市场信息或空字典
        """
        return self.markets.get(symbol, {})
    
    def get_trading_rules(self, symbol: str) -> Dict[str, Any]:
        """
        从缓存获取交易规则
        
        Args:
            symbol: 交易对符号
            
        Returns:
            交易规则或空字典
        """
        return self.trading_rules.get(symbol, {})
    
    def get_precision(self, symbol: str) -> Dict[str, int]:
        """
        获取交易对精度信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            精度信息字典 {'price': 价格精度, 'amount': 数量精度}
        """
        market_info = self.get_market_info(symbol)
        precision = market_info.get('precision', {})
        return {
            'price': precision.get('price', 8),
            'amount': precision.get('amount', 8)
        }