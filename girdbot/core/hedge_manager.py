"""
对冲管理器 - 处理对冲交易逻辑
"""
import asyncio
import time
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from girdbot.exchange.exchange_manager import ExchangeManager
from girdbot.utils.helpers import round_to_precision
from girdbot.utils.logger import get_logger

logger = get_logger("hedge_manager")

class HedgeManager:
    """对冲管理器，负责处理对冲交易逻辑"""
    
    def __init__(self, exchange_manager: ExchangeManager):
        """
        初始化对冲管理器
        
        Args:
            exchange_manager: 交易所管理器实例
        """
        self.exchange_manager = exchange_manager
        self.hedge_strategies: Dict[str, Dict] = {}  # 策略ID -> 对冲配置
        self.hedge_orders: Dict[str, Dict] = {}  # 原始订单ID -> 对冲订单信息
        self.reverse_lookup: Dict[str, str] = {}  # 对冲订单ID -> 原始订单ID
    
    async def initialize_for_strategy(self, strategy):
        """
        为策略初始化对冲设置
        
        Args:
            strategy: 策略实例
        """
        strategy_id = strategy.strategy_id
        trading_pair = strategy.trading_pair
        
        # 获取对冲交易所
        hedge_exchanges = self.exchange_manager.get_hedge_exchanges()
        if not hedge_exchanges:
            logger.warning(f"策略 {strategy_id} 启用了对冲但没有找到对冲交易所")
            return False
            
        # 初始化对冲配置
        self.hedge_strategies[strategy_id] = {
            "trading_pair": trading_pair,
            "exchanges": hedge_exchanges,
            "price_precision": Decimal("0.00000001"),  # 默认值，将在首次下单时更新
            "amount_precision": Decimal("0.00000001"),  # 默认值，将在首次下单时更新
            "initialized": True,
            "last_update": time.time()
        }
        
        logger.info(f"策略 {strategy_id} 对冲模式已初始化，对冲交易所: {[ex.name for ex in hedge_exchanges]}")
        return True
    
    async def create_hedge_order(self, strategy_id: str, side: str, amount: Decimal, price: Decimal, level_id: str, original_order_id: Optional[str] = None):
        """
        创建对冲订单
        
        Args:
            strategy_id: 策略ID
            side: 交易方向 (buy/sell)
            amount: 交易数量
            price: 交易价格
            level_id: 对应的网格级别ID
            original_order_id: 原始订单ID（如果有）
        
        Returns:
            对冲订单ID列表
        """
        # 检查策略是否已初始化对冲
        if strategy_id not in self.hedge_strategies:
            logger.warning(f"策略 {strategy_id} 未初始化对冲模式")
            return []
            
        hedge_config = self.hedge_strategies[strategy_id]
        trading_pair = hedge_config["trading_pair"]
        hedge_exchanges = hedge_config["exchanges"]
        
        # 对冲需要反向交易
        hedge_side = "sell" if side == "buy" else "buy"
        
        # 获取交易所精度要求
        if hedge_exchanges and len(hedge_exchanges) > 0:
            await self._update_precision_if_needed(strategy_id, hedge_exchanges[0], trading_pair)
        
        # 应用精度
        price_precision = hedge_config["price_precision"]
        amount_precision = hedge_config["amount_precision"]
        
        rounded_price = round_to_precision(price, price_precision)
        rounded_amount = round_to_precision(amount, amount_precision)
        
        # 生成一个原始订单ID (如果未提供)
        if not original_order_id:
            original_order_id = f"primary_{uuid.uuid4().hex[:8]}"
            
        # 在每个对冲交易所下单
        hedge_order_ids = []
        hedge_order_info = {
            "strategy_id": strategy_id,
            "level_id": level_id,
            "side": hedge_side,
            "amount": str(rounded_amount),
            "price": str(rounded_price),
            "status": "creating",
            "orders": {}
        }
        
        for exchange in hedge_exchanges:
            try:
                # 创建对冲订单
                order_id = await exchange.create_limit_order(
                    symbol=trading_pair,
                    side=hedge_side,
                    amount=rounded_amount,
                    price=rounded_price
                )
                
                if order_id:
                    hedge_order_ids.append(order_id)
                    # 记录对冲订单信息
                    hedge_order_info["orders"][order_id] = {
                        "exchange_name": exchange.name,
                        "exchange_id": exchange.id,
                        "status": "open",
                        "timestamp": time.time()
                    }
                    # 添加反向查找
                    self.reverse_lookup[order_id] = original_order_id
                    
                    logger.info(f"已在交易所 {exchange.name} 创建对冲订单: {order_id} {hedge_side} {rounded_amount} @ {rounded_price}")
            except Exception as e:
                logger.error(f"在交易所 {exchange.name} 创建对冲订单失败: {e}")
        
        # 保存对冲订单信息
        if hedge_order_ids:
            hedge_order_info["status"] = "open"
            self.hedge_orders[original_order_id] = hedge_order_info
            logger.info(f"为原始订单 {original_order_id} 创建了 {len(hedge_order_ids)} 个对冲订单")
        else:
            logger.warning(f"未能为原始订单 {original_order_id} 创建任何对冲订单")
            
        return hedge_order_ids
    
    async def cancel_hedge_orders(self, original_order_id: str):
        """
        取消与原始订单关联的所有对冲订单
        
        Args:
            original_order_id: 原始订单ID
        """
        if original_order_id not in self.hedge_orders:
            logger.warning(f"找不到原始订单 {original_order_id} 的对冲订单")
            return
            
        hedge_order_info = self.hedge_orders[original_order_id]
        strategy_id = hedge_order_info["strategy_id"]
        trading_pair = self.hedge_strategies[strategy_id]["trading_pair"]
        
        for order_id, order_data in hedge_order_info["orders"].items():
            if order_data["status"] == "open":
                exchange_name = order_data["exchange_name"]
                exchange = self.exchange_manager.get_exchange_by_name(exchange_name)
                
                if not exchange:
                    logger.warning(f"找不到交易所 {exchange_name}")
                    continue
                    
                try:
                    # 取消对冲订单
                    await exchange.cancel_order(order_id, trading_pair)
                    order_data["status"] = "canceled"
                    order_data["cancel_time"] = time.time()
                    logger.info(f"已取消对冲订单: {order_id} 在交易所 {exchange_name}")
                except Exception as e:
                    logger.error(f"取消对冲订单 {order_id} 失败: {e}")
        
        # 更新对冲订单状态
        hedge_order_info["status"] = "canceled"
        self.hedge_orders[original_order_id] = hedge_order_info
    
    async def update(self, strategy_id: str):
        """
        更新指定策略的对冲订单状态
        
        Args:
            strategy_id: 策略ID
        """
        if strategy_id not in self.hedge_strategies:
            return
            
        # 找到该策略的所有对冲订单
        strategy_hedge_orders = {
            order_id: order_info for order_id, order_info in self.hedge_orders.items()
            if order_info["strategy_id"] == strategy_id and order_info["status"] == "open"
        }
        
        if not strategy_hedge_orders:
            return
            
        # 按交易所分组检查订单
        for original_order_id, order_info in strategy_hedge_orders.items():
            trading_pair = self.hedge_strategies[strategy_id]["trading_pair"]
            
            # 检查每个对冲订单的状态
            for hedge_order_id, hedge_order_data in order_info["orders"].items():
                if hedge_order_data["status"] != "open":
                    continue
                    
                exchange_name = hedge_order_data["exchange_name"]
                exchange = self.exchange_manager.get_exchange_by_name(exchange_name)
                
                if not exchange:
                    continue
                    
                try:
                    # 查询订单状态
                    order_status = await exchange.fetch_order(hedge_order_id, trading_pair)
                    
                    # 更新订单状态
                    if order_status["status"] == "closed":
                        hedge_order_data["status"] = "filled"
                        hedge_order_data["filled_time"] = time.time()
                        logger.info(f"对冲订单 {hedge_order_id} 已成交")
                    elif order_status["status"] == "canceled":
                        hedge_order_data["status"] = "canceled"
                        hedge_order_data["cancel_time"] = time.time()
                        logger.info(f"对冲订单 {hedge_order_id} 已取消")
                except Exception as e:
                    logger.error(f"检查对冲订单 {hedge_order_id} 状态时出错: {e}")
    
    async def handle_order_filled(self, original_order_id: str):
        """
        处理原始订单成交事件，检查并更新对冲订单
        
        Args:
            original_order_id: 原始订单ID
        """
        if original_order_id not in self.hedge_orders:
            return
            
        hedge_order_info = self.hedge_orders[original_order_id]
        
        # 检查是否所有对冲订单都已成交
        all_filled = True
        for order_id, order_data in hedge_order_info["orders"].items():
            if order_data["status"] != "filled":
                all_filled = False
                break
                
        if all_filled:
            hedge_order_info["status"] = "filled"
            logger.info(f"原始订单 {original_order_id} 的所有对冲订单都已成交")
        else:
            # 可以添加额外的对冲逻辑，如取消未成交的对冲订单
            pass
    
    async def _update_precision_if_needed(self, strategy_id: str, exchange, trading_pair: str):
        """
        更新交易对精度信息(如果需要)
        
        Args:
            strategy_id: 策略ID
            exchange: 交易所实例
            trading_pair: 交易对
        """
        hedge_config = self.hedge_strategies[strategy_id]
        
        try:
            # 获取市场信息
            market_info = await exchange.fetch_market_info(trading_pair)
            
            # 更新精度信息
            price_precision = Decimal(f"0.{'0' * (market_info.get('precision', {}).get('price', 8) - 1)}1")
            amount_precision = Decimal(f"0.{'0' * (market_info.get('precision', {}).get('amount', 8) - 1)}1")
            
            hedge_config["price_precision"] = price_precision
            hedge_config["amount_precision"] = amount_precision
            
        except Exception as e:
            logger.error(f"获取交易所精度信息失败: {e}")
    
    def get_hedge_orders_by_strategy(self, strategy_id: str) -> Dict:
        """
        获取指定策略的所有对冲订单
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            该策略的所有对冲订单字典
        """
        return {
            order_id: order_info for order_id, order_info in self.hedge_orders.items()
            if order_info["strategy_id"] == strategy_id
        }
    
    def get_hedge_order_by_original(self, original_order_id: str) -> Optional[Dict]:
        """
        通过原始订单ID获取对冲订单信息
        
        Args:
            original_order_id: 原始订单ID
            
        Returns:
            对冲订单信息或None
        """
        return self.hedge_orders.get(original_order_id)
    
    def get_original_order_id(self, hedge_order_id: str) -> Optional[str]:
        """
        通过对冲订单ID获取原始订单ID
        
        Args:
            hedge_order_id: 对冲订单ID
            
        Returns:
            原始订单ID或None
        """
        return self.reverse_lookup.get(hedge_order_id)
    
    async def close_all_hedge_positions(self, strategy_id: str, trading_pair: str = None):
        """
        关闭指定策略的所有对冲仓位
        
        Args:
            strategy_id: 策略ID
            trading_pair: 交易对，如果为None则使用策略配置中的交易对
        """
        if strategy_id not in self.hedge_strategies:
            logger.warning(f"策略 {strategy_id} 未初始化对冲模式")
            return
            
        hedge_config = self.hedge_strategies[strategy_id]
        # 如果未提供交易对，则使用策略配置中的交易对
        if trading_pair is None:
            trading_pair = hedge_config["trading_pair"]
            
        hedge_exchanges = hedge_config["exchanges"]
        
        if not hedge_exchanges:
            logger.warning(f"策略 {strategy_id} 没有配置对冲交易所")
            return
            
        logger.info(f"关闭策略 {strategy_id} 的所有对冲仓位，交易对: {trading_pair}")
        
        for exchange in hedge_exchanges:
            try:
                # 获取当前持仓
                positions = await exchange.fetch_positions(trading_pair)
                
                if not positions:
                    logger.info(f"交易所 {exchange.name} 没有 {trading_pair} 的持仓")
                    continue
                    
                logger.info(f"交易所 {exchange.name} 有 {len(positions)} 个 {trading_pair} 持仓需要平仓")
                
                for position in positions:
                    position_side = position.get("side")
                    position_size = position.get("size")
                    
                    # 确保持仓数据有效
                    if not position_side or not position_size:
                        logger.warning(f"持仓数据不完整: {position}")
                        continue
                        
                    position_amount = abs(float(position_size))
                    
                    if position_amount > 0:
                        # 创建市价单平仓
                        close_side = "sell" if position_side == "long" else "buy"
                        
                        logger.info(f"在交易所 {exchange.name} 平仓: {close_side} {position_amount} {trading_pair}")
                        
                        try:
                            # 尝试使用reduce_only参数平仓
                            await exchange.create_market_order(
                                symbol=trading_pair,
                                side=close_side,
                                amount=position_amount,
                                reduce_only=True
                            )
                            logger.info(f"交易所 {exchange.name} 的 {position_side} 持仓已成功平仓")
                        except Exception as e1:
                            logger.error(f"使用reduce_only平仓失败: {e1}", exc_info=True)
                            try:
                                # 如果reduce_only参数失败，尝试不带该参数的平仓
                                await exchange.create_market_order(
                                    symbol=trading_pair,
                                    side=close_side,
                                    amount=position_amount
                                )
                                logger.info(f"交易所 {exchange.name} 的 {position_side} 持仓已成功平仓(不使用reduce_only)")
                            except Exception as e2:
                                logger.error(f"平仓失败: {e2}", exc_info=True)
                
                # 验证平仓结果
                try:
                    verification_positions = await exchange.fetch_positions(trading_pair)
                    if verification_positions:
                        for pos in verification_positions:
                            if abs(float(pos.get("size", 0))) > 0:
                                logger.warning(f"交易所 {exchange.name} 的 {pos.get('side')} 持仓平仓失败，仍有 {pos.get('size')} 未平仓")
                    else:
                        logger.info(f"交易所 {exchange.name} 的所有持仓已成功平仓")
                except Exception as e:
                    logger.error(f"验证平仓结果失败: {e}", exc_info=True)
                    
            except Exception as e:
                logger.error(f"在交易所 {exchange.name} 关闭对冲仓位失败: {e}", exc_info=True)
                
    def to_json(self) -> Dict:
        """
        将对冲管理器状态转换为JSON可序列化的字典
        
        Returns:
            状态字典
        """
        return {
            "hedge_strategies": self.hedge_strategies,
            "hedge_orders": self.hedge_orders,
            "reverse_lookup": self.reverse_lookup
        }
    
    @classmethod
    def from_json(cls, data: Dict, exchange_manager):
        """
        从JSON数据恢复对冲管理器状态
        
        Args:
            data: 状态字典
            exchange_manager: 交易所管理器实例
            
        Returns:
            对冲管理器实例
        """
        hedge_manager = cls(exchange_manager)
        hedge_manager.hedge_strategies = data.get("hedge_strategies", {})
        hedge_manager.hedge_orders = data.get("hedge_orders", {})
        hedge_manager.reverse_lookup = data.get("reverse_lookup", {})
        return hedge_manager