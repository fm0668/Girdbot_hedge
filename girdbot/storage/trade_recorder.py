"""
交易记录器 - 记录和管理交易数据
"""
import os
import time
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional
import asyncio

from girdbot.storage.file_storage import FileStorage
from girdbot.utils.logger import get_logger

logger = get_logger("trade_recorder")

class Trade:
    """交易记录类"""
    
    def __init__(self, 
                 trade_id: str,
                 strategy_id: str,
                 order_id: str,
                 trading_pair: str,
                 side: str,
                 price: Decimal,
                 amount: Decimal,
                 timestamp: float,
                 fee: Optional[Decimal] = None,
                 fee_currency: Optional[str] = None):
        """
        初始化交易记录
        
        Args:
            trade_id: 交易ID
            strategy_id: 策略ID
            order_id: 订单ID
            trading_pair: 交易对
            side: 交易方向(buy/sell)
            price: 成交价格
            amount: 成交数量
            timestamp: 成交时间戳
            fee: 手续费(可选)
            fee_currency: 手续费货币(可选)
        """
        self.trade_id = trade_id
        self.strategy_id = strategy_id
        self.order_id = order_id
        self.trading_pair = trading_pair
        self.side = side
        self.price = price
        self.amount = amount
        self.timestamp = timestamp
        self.fee = fee
        self.fee_currency = fee_currency
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trade_id": self.trade_id,
            "strategy_id": self.strategy_id,
            "order_id": self.order_id,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "price": str(self.price),
            "amount": str(self.amount),
            "timestamp": self.timestamp,
            "fee": str(self.fee) if self.fee else None,
            "fee_currency": self.fee_currency
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """从字典创建交易记录"""
        return cls(
            trade_id=data["trade_id"],
            strategy_id=data["strategy_id"],
            order_id=data["order_id"],
            trading_pair=data["trading_pair"],
            side=data["side"],
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            timestamp=data["timestamp"],
            fee=Decimal(data["fee"]) if data.get("fee") else None,
            fee_currency=data.get("fee_currency")
        )
        
    @property
    def value(self) -> Decimal:
        """交易价值(价格 × 数量)"""
        return self.price * self.amount

class TradeRecorder:
    """交易记录器，记录和管理所有交易"""
    
    def __init__(self, data_dir: str = "./data"):
        """
        初始化交易记录器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.storage = FileStorage(os.path.join(data_dir, "trades"))
        self.trades_cache: Dict[str, List[Dict[str, Any]]] = {}  # 策略ID -> 交易记录列表
        self._cache_initialized: Dict[str, bool] = {}  # 策略ID -> 缓存是否已初始化
        self._lock = asyncio.Lock()  # 用于保护缓存访问的锁
    
    def _get_trades_file(self, strategy_id: str) -> str:
        """
        获取策略交易记录文件名
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            文件名
        """
        return f"{strategy_id}_trades.json"
    
    async def _ensure_cache_initialized(self, strategy_id: str):
        """
        确保缓存已初始化
        
        Args:
            strategy_id: 策略ID
        """
        if strategy_id in self._cache_initialized and self._cache_initialized[strategy_id]:
            return
            
        async with self._lock:
            if strategy_id in self._cache_initialized and self._cache_initialized[strategy_id]:
                return
                
            filename = self._get_trades_file(strategy_id)
            trades_data = await self.storage.load_json(filename)
            
            if trades_data:
                self.trades_cache[strategy_id] = trades_data
            else:
                self.trades_cache[strategy_id] = []
                
            self._cache_initialized[strategy_id] = True
    
    def record_trade(self, strategy_id: str, order_id: str, trading_pair: str, 
                    side: str, price: Decimal, amount: Decimal, timestamp: float,
                    fee: Optional[Decimal] = None, fee_currency: Optional[str] = None) -> str:
        """
        记录交易
        
        Args:
            strategy_id: 策略ID
            order_id: 订单ID
            trading_pair: 交易对
            side: 交易方向(buy/sell)
            price: 成交价格
            amount: 成交数量
            timestamp: 成交时间戳
            fee: 手续费(可选)
            fee_currency: 手续费货币(可选)
            
        Returns:
            交易ID
        """
        # 生成交易ID
        trade_id = f"{strategy_id}_{int(timestamp)}_{order_id[-8:]}"
        
        # 创建交易记录
        trade = Trade(
            trade_id=trade_id,
            strategy_id=strategy_id,
            order_id=order_id,
            trading_pair=trading_pair,
            side=side,
            price=price,
            amount=amount,
            timestamp=timestamp,
            fee=fee,
            fee_currency=fee_currency
        )
        
        # 确保缓存已初始化
        if strategy_id not in self.trades_cache:
            self.trades_cache[strategy_id] = []
            self._cache_initialized[strategy_id] = True
            
        # 添加到缓存
        self.trades_cache[strategy_id].append(trade.to_dict())
        
        # 保存到文件
        self._save_trades(strategy_id)
        
        logger.debug(f"记录交易: {trade_id}, {side} {amount} {trading_pair} @ {price}")
        
        return trade_id
    
    def _save_trades(self, strategy_id: str) -> bool:
        """
        保存策略的交易记录
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否成功保存
        """
        if strategy_id not in self.trades_cache:
            return False
            
        filename = self._get_trades_file(strategy_id)
        return self.storage.save_json_sync(filename, self.trades_cache[strategy_id])
    
    async def get_trades_by_strategy(self, strategy_id: str) -> List[Dict[str, Any]]:
        """
        获取策略的所有交易记录
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            交易记录列表
        """
        await self._ensure_cache_initialized(strategy_id)
        return self.trades_cache.get(strategy_id, [])
    
    async def get_trades_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        """
        获取订单的所有交易记录
        
        Args:
            order_id: 订单ID
            
        Returns:
            交易记录列表
        """
        result = []
        
        # 遍历所有策略的交易记录
        for strategy_id in self.list_strategies():
            await self._ensure_cache_initialized(strategy_id)
            
            if strategy_id in self.trades_cache:
                for trade in self.trades_cache[strategy_id]:
                    if trade["order_id"] == order_id:
                        result.append(trade)
        
        return result
    
    async def get_trade_by_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        通过ID获取交易记录
        
        Args:
            trade_id: 交易ID
            
        Returns:
            交易记录或None
        """
        # 提取策略ID
        parts = trade_id.split('_')
        if len(parts) < 2:
            return None
            
        strategy_id = parts[0]
        
        await self._ensure_cache_initialized(strategy_id)
        
        if strategy_id in self.trades_cache:
            for trade in self.trades_cache[strategy_id]:
                if trade["trade_id"] == trade_id:
                    return trade
        
        return None
    
    def list_strategies(self) -> List[str]:
        """
        列出所有有交易记录的策略
        
        Returns:
            策略ID列表
        """
        files = self.storage.list_files("*_trades.json")
        return [f.replace("_trades.json", "") for f in files]
    
    async def calculate_profit(self, strategy_id: str) -> Dict[str, Any]:
        """
        计算策略的盈亏
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            包含盈亏信息的字典
        """
        trades = await self.get_trades_by_strategy(strategy_id)
        
        if not trades:
            return {
                "strategy_id": strategy_id,
                "total_buy_volume": 0,
                "total_sell_volume": 0,
                "total_buy_value": 0,
                "total_sell_value": 0,
                "realized_profit": 0,
                "total_fees": 0
            }
        
        total_buy_volume = Decimal("0")
        total_sell_volume = Decimal("0")
        total_buy_value = Decimal("0")
        total_sell_value = Decimal("0")
        total_fees = Decimal("0")
        
        for trade in trades:
            price = Decimal(trade["price"])
            amount = Decimal(trade["amount"])
            value = price * amount
            
            if trade["side"] == "buy":
                total_buy_volume += amount
                total_buy_value += value
            else:  # sell
                total_sell_volume += amount
                total_sell_value += value
                
            if trade.get("fee") is not None:
                total_fees += Decimal(trade["fee"])
        
        # 计算已实现盈亏
        if total_buy_volume > 0 and total_sell_volume > 0:
            # 部分平仓情况下的盈亏计算
            avg_buy_price = total_buy_value / total_buy_volume
            realized_profit = total_sell_value - (total_sell_volume * avg_buy_price)
        else:
            realized_profit = Decimal("0")
        
        return {
            "strategy_id": strategy_id,
            "total_buy_volume": str(total_buy_volume),
            "total_sell_volume": str(total_sell_volume),
            "total_buy_value": str(total_buy_value),
            "total_sell_value": str(total_sell_value),
            "realized_profit": str(realized_profit),
            "total_fees": str(total_fees)
        }
    
    async def export_trades_to_csv(self, strategy_id: str, filepath: str) -> bool:
        """
        将策略交易记录导出为CSV文件
        
        Args:
            strategy_id: 策略ID
            filepath: 导出文件路径
            
        Returns:
            是否成功导出
        """
        trades = await self.get_trades_by_strategy(strategy_id)
        
        if not trades:
            logger.warning(f"策略 {strategy_id} 没有交易记录")
            return False
        
        try:
            import csv
            import datetime
            
            with open(filepath, 'w', newline='') as csvfile:
                fieldnames = ['trade_id', 'timestamp', 'datetime', 'order_id', 
                              'trading_pair', 'side', 'price', 'amount', 
                              'value', 'fee', 'fee_currency']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for trade in trades:
                    # 计算交易价值
                    price = Decimal(trade["price"])
                    amount = Decimal(trade["amount"])
                    value = price * amount
                    
                    # 转换时间戳为可读格式
                    dt = datetime.datetime.fromtimestamp(trade["timestamp"])
                    datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    writer.writerow({
                        'trade_id': trade["trade_id"],
                        'timestamp': trade["timestamp"],
                        'datetime': datetime_str,
                        'order_id': trade["order_id"],
                        'trading_pair': trade["trading_pair"],
                        'side': trade["side"],
                        'price': trade["price"],
                        'amount': trade["amount"],
                        'value': str(value),
                        'fee': trade.get("fee", ""),
                        'fee_currency': trade.get("fee_currency", "")
                    })
            
            logger.info(f"已导出策略 {strategy_id} 的交易记录到 {filepath}")
            return True
        except Exception as e:
            logger.error(f"导出交易记录失败: {e}")
            return False
    
    async def clear_old_trades(self, strategy_id: str, days: int = 30) -> int:
        """
        清理旧的交易记录
        
        Args:
            strategy_id: 策略ID
            days: 保留多少天内的交易记录
            
        Returns:
            清理的交易记录数量
        """
        await self._ensure_cache_initialized(strategy_id)
        
        if strategy_id not in self.trades_cache:
            return 0
            
        # 计算截止时间
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        # 备份交易记录
        backup_filename = f"{strategy_id}_trades_backup_{int(time.time())}.json"
        self.storage.save_json_sync(backup_filename, self.trades_cache[strategy_id])
        
        # 筛选保留的交易记录
        original_count = len(self.trades_cache[strategy_id])
        self.trades_cache[strategy_id] = [
            trade for trade in self.trades_cache[strategy_id]
            if trade["timestamp"] >= cutoff_time
        ]
        
        # 保存更新后的交易记录
        self._save_trades(strategy_id)
        
        removed_count = original_count - len(self.trades_cache[strategy_id])
        logger.info(f"已清理策略 {strategy_id} 的 {removed_count} 条旧交易记录")
        
        return removed_count