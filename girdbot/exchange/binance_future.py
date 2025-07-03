"""
币安合约接口实现
"""
import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any

import ccxt.async_support as ccxt

from girdbot.exchange.exchange_base import ExchangeBase
from girdbot.utils.logger import get_logger

logger = get_logger("binance_future")

class BinanceFutureExchange(ExchangeBase):
    """币安合约交易所接口"""
    
    def __init__(self, api_key: str, api_secret: str, account_alias: str = None, testnet: bool = False):
        """
        初始化币安合约接口
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            account_alias: 账户别名(可选)
            testnet: 是否使用测试网络
        """
        super().__init__(api_key, api_secret, "binance_future", account_alias)
        
        # 创建CCXT交易所实例
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,  # 启用请求频率限制
            'options': {
                'defaultType': 'future',  # 默认为合约交易
                'adjustForTimeDifference': True,  # 调整时间差异
                'recvWindow': 10000,  # 接收窗口设置
                'hedgeMode': True  # 启用对冲模式
            }
        })
        
        # 设置测试网
        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info(f"交易所 {self.id} 运行在测试网模式")
    
    async def initialize(self):
        """初始化交易所连接"""
        try:
            logger.info(f"初始化交易所连接: {self.id}")
            
            # 加载市场信息
            await self.exchange.load_markets()
            self.markets = self.exchange.markets
            self.symbols = self.exchange.symbols
            
            # 提取交易规则
            for symbol, market in self.markets.items():
                self.trading_rules[symbol] = {
                    'min_price': market.get('limits', {}).get('price', {}).get('min'),
                    'max_price': market.get('limits', {}).get('price', {}).get('max'),
                    'min_amount': market.get('limits', {}).get('amount', {}).get('min'),
                    'max_amount': market.get('limits', {}).get('amount', {}).get('max'),
                    'min_notional': market.get('limits', {}).get('cost', {}).get('min'),
                    'precision': market.get('precision', {})
                }
            
            # 设置对冲模式
            try:
                await self._set_hedge_mode(True)
            except Exception as e:
                logger.warning(f"设置对冲模式失败: {e}")
            
            # 测试API权限
            await self.exchange.fetch_balance()
            
            self.initialized = True
            logger.info(f"交易所 {self.id} 初始化完成")
        except Exception as e:
            logger.error(f"交易所 {self.id} 初始化失败: {e}")
            self.initialized = False
            raise
    
    async def _set_hedge_mode(self, hedge_mode: bool):
        """
        设置对冲模式
        
        Args:
            hedge_mode: True为对冲模式，False为单向模式
        """
        try:
            # 先检查当前的持仓模式
            current_mode = await self.exchange.fapiPrivateGetPositionSideDual()
            current_hedge_mode = current_mode.get('dualSidePosition', False)
            
            # 如果当前模式与目标模式相同，则不需要更改
            if (current_hedge_mode and hedge_mode) or (not current_hedge_mode and not hedge_mode):
                logger.info(f"交易所 {self.id} 已经是{'对冲' if hedge_mode else '单向'}模式，无需更改")
                return
            
            # 设置持仓模式
            mode = 'hedge' if hedge_mode else 'oneWay'
            params = {'dualSidePosition': 'true' if hedge_mode else 'false'}
            await self.exchange.fapiPrivatePostPositionSideDual(params)
            logger.info(f"交易所 {self.id} 已设置为{mode}模式")
        except Exception as e:
            error_str = str(e)
            # 处理特定的错误码
            if '"code":-4059' in error_str and '"msg":"No need to change position side."' in error_str:
                logger.info(f"交易所 {self.id} 已经是{'对冲' if hedge_mode else '单向'}模式，无需更改")
            elif "已经处于" in error_str or "already" in error_str.lower():
                logger.info(f"交易所 {self.id} 已经是{'对冲' if hedge_mode else '单向'}模式")
            else:
                logger.warning(f"设置对冲模式失败: {self.id} {e}")
                # 不抛出异常，因为这不是致命错误
    
    async def close(self):
        """关闭交易所连接"""
        try:
            if hasattr(self, 'exchange') and self.exchange:
                # 确保交易所连接被正确关闭
                try:
                    await self.exchange.close()
                except Exception as e:
                    logger.error(f"关闭交易所 {self.id} 连接时出错: {e}")
                
                # 确保所有aiohttp会话被关闭
                if hasattr(self.exchange, 'session') and self.exchange.session:
                    try:
                        if not self.exchange.session.closed:
                            await self.exchange.session.close()
                            # 等待会话完全关闭
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"关闭交易所 {self.id} 会话时出错: {e}")
                
                # 尝试获取和关闭所有可能的会话
                try:
                    # 尝试获取CCXT内部的客户端会话
                    if hasattr(self.exchange, 'client'):
                        client = getattr(self.exchange, 'client')
                        if hasattr(client, 'session') and client.session:
                            if not client.session.closed:
                                await client.session.close()
                                await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"关闭交易所 {self.id} 内部客户端会话时出错: {e}")
                
                # 强制清理引用
                self.exchange = None
                
                logger.info(f"交易所 {self.id} 连接已关闭")
        except Exception as e:
            logger.error(f"关闭交易所 {self.id} 连接时出错: {e}")
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对行情数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含行情数据的字典
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"获取行情数据失败 {symbol}: {e}")
            raise
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        获取账户余额
        
        Returns:
            包含余额数据的字典
        """
        try:
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            raise
    
    async def fetch_market_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对市场信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含市场信息的字典
        """
        try:
            if not self.markets:
                await self.exchange.load_markets()
                self.markets = self.exchange.markets
                
            if symbol in self.markets:
                return self.markets[symbol]
            else:
                logger.warning(f"找不到交易对 {symbol} 的市场信息")
                return {}
        except Exception as e:
            logger.error(f"获取市场信息失败 {symbol}: {e}")
            raise
    
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
        try:
            # 转换Decimal为float，因为CCXT需要float类型
            amount_float = float(amount)
            price_float = float(price)
            
            # 设置持仓方向参数
            params = {
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
            
            # 创建订单
            order = await self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=amount_float,
                price=price_float,
                params=params
            )
            
            logger.info(f"创建限价单成功: {side} {amount} {symbol} @ {price}, 订单ID: {order['id']}")
            return order['id']
        except Exception as e:
            logger.error(f"创建限价单失败: {e}")
            raise
    
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
        try:
            # 转换Decimal为float
            amount_float = float(amount)
            
            # 设置持仓方向参数
            params = {
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
            
            # 创建订单
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount_float,
                params=params
            )
            
            logger.info(f"创建市价单成功: {side} {amount} {symbol}, 订单ID: {order['id']}")
            return order['id']
        except Exception as e:
            logger.error(f"创建市价单失败: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            是否成功取消
        """
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"取消订单成功: {order_id}, 交易对: {symbol}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败 {order_id}: {e}")
            return False
    
    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            包含订单信息的字典
        """
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"获取订单信息失败 {order_id}: {e}")
            raise
    
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
        try:
            orders = await self.exchange.fetch_orders(symbol=symbol, since=since, limit=limit)
            return orders
        except Exception as e:
            logger.error(f"获取订单列表失败: {e}")
            raise
    
    async def fetch_orders_by_ids(self, order_ids: List[str], symbol: str = None) -> Dict[str, Dict[str, Any]]:
        """
        批量获取订单信息
        
        Args:
            order_ids: 订单ID列表
            symbol: 交易对符号(可选)
            
        Returns:
            订单ID -> 订单信息的字典
        """
        result = {}
        
        for order_id in order_ids:
            try:
                order = await self.fetch_order(order_id, symbol)
                result[order_id] = order
                # 添加小延迟避免API限流
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"获取订单 {order_id} 信息失败: {e}")
                result[order_id] = {"status": "error", "error": str(e)}
        
        return result
    
    async def fetch_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对符号(可选)
            
        Returns:
            持仓列表
        """
        try:
            if symbol:
                positions = await self.exchange.fetch_positions([symbol])
            else:
                positions = await self.exchange.fetch_positions()
                
            # 筛选有持仓的仓位
            active_positions = [
                position for position in positions
                if abs(float(position.get('contracts', 0))) > 0
            ]
            
            return active_positions
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return []
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        设置杠杆倍数
        
        Args:
            symbol: 交易对符号
            leverage: 杠杆倍数
            
        Returns:
            是否设置成功
        """
        try:
            result = await self.exchange.fapiPrivatePostLeverage({
                'symbol': symbol.replace('/', ''),
                'leverage': leverage
            })
            logger.info(f"设置杠杆倍数成功: {symbol} -> {leverage}x")
            return True
        except Exception as e:
            logger.error(f"设置杠杆倍数失败 {symbol}: {e}")
            return False