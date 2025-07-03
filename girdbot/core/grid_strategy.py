"""
网格策略实现
"""
import asyncio
import time
import uuid
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple

from girdbot.core.hedge_manager import HedgeManager
from girdbot.core.order_manager import OrderManager
from girdbot.exchange.exchange_manager import ExchangeManager
from girdbot.storage.grid_state import GridStateManager
from girdbot.storage.trade_recorder import TradeRecorder
from girdbot.utils.helpers import round_to_precision
from girdbot.utils.logger import get_logger

logger = get_logger("grid_strategy")

class GridLevel:
    """网格级别，表示网格中的一个价格点位"""
    
    def __init__(self, id: str, price: Decimal, amount: Decimal, 
                 buy_order_id: Optional[str] = None,
                 sell_order_id: Optional[str] = None):
        """
        初始化网格级别
        
        Args:
            id: 级别唯一标识符
            price: 价格点位
            amount: 交易金额
            buy_order_id: 买单ID
            sell_order_id: 卖单ID
        """
        self.id = id
        self.price = price
        self.amount = amount
        self.buy_order_id = buy_order_id
        self.sell_order_id = sell_order_id
        self.status = "READY"  # READY, BUYING, BOUGHT, SELLING, SOLD
        self.last_update = time.time()
        
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "price": str(self.price),
            "amount": str(self.amount),
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "status": self.status,
            "last_update": self.last_update
        }
        
    @classmethod
    def from_dict(cls, data):
        """从字典创建级别"""
        level = cls(
            id=data["id"],
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            buy_order_id=data.get("buy_order_id"),
            sell_order_id=data.get("sell_order_id")
        )
        level.status = data.get("status", "READY")
        level.last_update = data.get("last_update", time.time())
        return level

class GridStrategy:
    """网格交易策略实现"""
    
    def __init__(self, strategy_id: str, config: dict,
                 exchange_manager: ExchangeManager,
                 state_manager: GridStateManager,
                 trade_recorder: TradeRecorder,
                 hedge_manager: Optional[HedgeManager] = None,
                 saved_state: Optional[dict] = None):
        """
        初始化网格策略
        
        Args:
            strategy_id: 策略ID
            config: 策略配置
            exchange_manager: 交易所管理器
            state_manager: 状态管理器
            trade_recorder: 交易记录器
            hedge_manager: 对冲管理器
            saved_state: 保存的状态(用于恢复)
        """
        self.strategy_id = strategy_id
        self.config = config
        self.exchange_manager = exchange_manager
        self.state_manager = state_manager
        self.trade_recorder = trade_recorder
        self.hedge_manager = hedge_manager
        
        # 解析配置
        self.trading_pair = config["symbol"]
        self.start_price = Decimal(str(config["low_price"]))
        self.end_price = Decimal(str(config["high_price"]))
        self.grid_levels = config["grid_number"]
        self.total_investment = Decimal(str(config["investment"]))
        self.enable_hedge = config.get("enable_hedge", False)
        self.order_type = config.get("order_type", "limit")
        self.is_future = config.get("is_future", True)
        
        # 风险控制参数
        risk_controls = config.get("risk_controls", {})
        self.max_price_deviation = Decimal(str(risk_controls.get("max_price_deviation", 5))) / 100
        self.stop_loss = Decimal(str(risk_controls.get("stop_loss", 10))) / 100
        
        # 策略状态
        self.initialized = False
        self.running = False
        self.grid_levels_data: List[GridLevel] = []
        self.order_manager = OrderManager()
        
        # 统计数据
        self.total_profit = Decimal("0")
        self.completed_trades = 0
        self.start_time = time.time()
        
        # 恢复状态(如果有)
        if saved_state:
            self._restore_state(saved_state)
    
    async def initialize(self):
        """初始化网格策略"""
        if self.initialized:
            return True
            
        logger.info(f"初始化策略 {self.strategy_id}...")
        
        # 获取主交易所
        self.primary_exchange = self.exchange_manager.get_primary_exchange()
        if not self.primary_exchange:
            logger.error(f"策略 {self.strategy_id} 初始化失败：没有找到主交易所")
            return False
            
        try:
            # 检查当前价格
            current_price = await self.get_current_price()
            logger.info(f"当前 {self.trading_pair} 价格: {current_price}")
            
            # 检查价格是否在设定范围内
            if not (self.start_price <= current_price <= self.end_price):
                logger.warning(
                    f"当前价格 {current_price} 不在设定范围 {self.start_price} - {self.end_price} 内，"
                    f"将使用当前价格作为中点重新计算网格"
                )
                # 重新计算网格范围
                price_range = self.end_price - self.start_price
                self.start_price = current_price - (price_range / 2)
                self.end_price = current_price + (price_range / 2)
                if self.start_price < 0:
                    self.start_price = Decimal("0.0001")
                    self.end_price = self.start_price + price_range
        except Exception as e:
            logger.error(f"策略 {self.strategy_id} 初始化时获取价格失败: {e}")
            return False
        
        # 如果没有恢复状态，则创建网格
        if not self.grid_levels_data:
            try:
                await self.calculate_grid_levels()
            except Exception as e:
                logger.error(f"策略 {self.strategy_id} 计算网格点位失败: {e}")
                return False
        
        # 初始化对冲模式(如果启用)
        if self.enable_hedge and self.hedge_manager:
            try:
                await self.hedge_manager.initialize_for_strategy(self)
            except Exception as e:
                logger.error(f"策略 {self.strategy_id} 初始化对冲管理器失败: {e}")
                # 继续运行，但对冲功能可能不可用
        
        self.initialized = True
        logger.info(f"策略 {self.strategy_id} 初始化完成")
        return True
        
    async def update(self):
        """更新策略，处理订单状态变化"""
        if not self.initialized:
            logger.warning("策略尚未初始化，无法更新")
            return
            
        # 检查当前价格
        current_price = await self.get_current_price()
        
        # 检查订单状态
        await self.check_order_status()
        
        # 检查并更新网格订单
        await self.update_grid_orders(current_price)
        
        # 处理对冲操作(如果启用)
        if self.enable_hedge and self.hedge_manager:
            await self.hedge_manager.update(self.strategy_id)
            
        # 计算并记录当前收益
        await self.calculate_profit()
        
        # 检查风险控制
        await self.check_risk_controls(current_price)
        
        # 保存状态
        self.save_state()
    
    async def calculate_grid_levels(self):
        """计算网格价格点位和订单数量"""
        logger.info(f"计算网格点位: {self.grid_levels} 级，范围 {self.start_price} - {self.end_price}")
        
        # 获取交易所精度信息
        price_precision, amount_precision = await self.get_exchange_precision()
        
        # 计算网格价格点位
        price_step = (self.end_price - self.start_price) / (self.grid_levels - 1) if self.grid_levels > 1 else Decimal("0")
        
        # 每个网格的投资金额
        amount_per_grid = self.total_investment / self.grid_levels
        
        # 创建网格级别
        self.grid_levels_data = []
        
        for i in range(self.grid_levels):
            # 计算价格
            price = self.start_price + (price_step * i)
            price = self._adjust_to_precision(price, price_precision)
            
            # 计算金额(以报价货币计)
            amount = amount_per_grid
            
            # 创建网格级别
            level_id = f"level_{i}"
            level = GridLevel(level_id, price, amount)
            self.grid_levels_data.append(level)
            
        logger.info(f"创建了 {len(self.grid_levels_data)} 个网格点位")
    
    async def check_order_status(self):
        """检查所有订单的状态"""
        # 获取所有活跃订单ID
        active_order_ids = set()
        for level in self.grid_levels_data:
            if level.buy_order_id:
                active_order_ids.add(level.buy_order_id)
            if level.sell_order_id:
                active_order_ids.add(level.sell_order_id)
        
        if not active_order_ids:
            return
            
        # 批量查询订单状态
        orders_info = await self.primary_exchange.fetch_orders_by_ids(
            list(active_order_ids), self.trading_pair
        )
        
        for order_id, order_info in orders_info.items():
            if order_info["status"] == "closed":
                # 订单已成交
                await self.handle_order_filled(order_id, order_info)
            elif order_info["status"] == "canceled":
                # 订单已取消
                await self.handle_order_canceled(order_id)
    
    async def update_grid_orders(self, current_price):
        """根据当前价格更新网格订单"""
        for level in self.grid_levels_data:
            # 根据级别状态和当前价格决定操作
            if level.status == "READY":
                # 准备状态 - 如果价格低于网格价格，创建买单
                if current_price < level.price:
                    await self.place_buy_order(level)
                # 如果价格高于网格价格，创建卖单
                elif current_price > level.price:
                    await self.place_sell_order(level)
            
            elif level.status == "BOUGHT" and not level.sell_order_id:
                # 已买入但没有卖单 - 创建卖单
                await self.place_sell_order(level)
                
            elif level.status == "SOLD" and not level.buy_order_id:
                # 已卖出但没有买单 - 创建买单
                await self.place_buy_order(level)
    
    async def place_buy_order(self, level: GridLevel):
        """在指定网格级别创建买单"""
        try:
            # 获取交易所精度信息
            price_precision, amount_precision = await self.get_exchange_precision()
            
            # 确保价格符合精度要求
            price = self._adjust_to_precision(level.price, price_precision)

            # 计算买单数量(基础货币)
            base_amount = self._adjust_to_precision(level.amount / price, amount_precision)
            
            logger.info(f"在价格 {price} 创建买单，金额: {base_amount}")
            
            # 创建买单
            order_id = await self.primary_exchange.create_limit_order(
                symbol=self.trading_pair,
                side="buy",
                amount=float(base_amount),
                price=float(price)
            )
            
            # 更新级别状态
            level.buy_order_id = order_id
            level.status = "BUYING"
            level.last_update = time.time()
            
            # 记录订单
            self.order_manager.add_order(order_id, {
                "level_id": level.id,
                "price": level.price,
                "amount": base_amount,
                "side": "buy",
                "status": "open",
                "timestamp": time.time()
            })
            
            # 如果启用对冲，创建对冲卖单
            if self.enable_hedge and self.hedge_manager:
                await self.hedge_manager.create_hedge_order(
                    self.strategy_id, "sell", base_amount, level.price, level.id
                )
            
            logger.info(f"买单已创建: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"创建买单失败: {e}", exc_info=True)
            return None
    
    async def place_sell_order(self, level: GridLevel):
        """在指定网格级别创建卖单"""
        try:
            # 获取交易所精度信息
            price_precision, amount_precision = await self.get_exchange_precision()

            # 确保价格符合精度要求
            price = self._adjust_to_precision(level.price, price_precision)
            
            # 计算卖单数量(基础货币)
            base_amount = self._adjust_to_precision(level.amount / price, amount_precision)
            
            logger.info(f"在价格 {price} 创建卖单，金额: {base_amount}")
            
            # 创建卖单
            order_id = await self.primary_exchange.create_limit_order(
                symbol=self.trading_pair,
                side="sell",
                amount=float(base_amount),
                price=float(price)
            )
            
            # 更新级别状态
            level.sell_order_id = order_id
            level.status = "SELLING"
            level.last_update = time.time()
            
            # 记录订单
            self.order_manager.add_order(order_id, {
                "level_id": level.id,
                "price": level.price,
                "amount": base_amount,
                "side": "sell",
                "status": "open",
                "timestamp": time.time()
            })
            
            # 如果启用对冲，创建对冲买单
            if self.enable_hedge and self.hedge_manager:
                await self.hedge_manager.create_hedge_order(
                    self.strategy_id, "buy", base_amount, level.price, level.id
                )
            
            logger.info(f"卖单已创建: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"创建卖单失败: {e}", exc_info=True)
            return None
    
    async def handle_order_filled(self, order_id, order_info):
        """处理订单成交事件"""
        # 获取订单信息
        order_data = self.order_manager.get_order(order_id)
        if not order_data:
            logger.warning(f"找不到订单信息: {order_id}")
            return
            
        level_id = order_data["level_id"]
        side = order_data["side"]
        price = order_data["price"]
        amount = order_data["amount"]
        
        # 更新订单状态
        order_data["status"] = "filled"
        order_data["filled_time"] = time.time()
        self.order_manager.update_order(order_id, order_data)
        
        # 更新网格级别状态
        level = next((l for l in self.grid_levels_data if l.id == level_id), None)
        if not level:
            logger.warning(f"找不到网格级别: {level_id}")
            return
            
        if side == "buy":
            level.status = "BOUGHT"
            level.buy_order_id = None
            # 买入后创建卖单
            await self.place_sell_order(level)
        else:  # sell
            level.status = "SOLD"
            level.sell_order_id = None
            # 卖出后创建买单
            await self.place_buy_order(level)
            
        # 记录成交
        self.trade_recorder.record_trade(
            strategy_id=self.strategy_id,
            order_id=order_id,
            trading_pair=self.trading_pair,
            side=side,
            price=price,
            amount=amount,
            timestamp=time.time()
        )
        
        self.completed_trades += 1
        
        logger.info(f"订单 {order_id} 已成交: {side} {amount} @ {price}")
    
    async def handle_order_canceled(self, order_id):
        """处理订单取消事件"""
        # 获取订单信息
        order_data = self.order_manager.get_order(order_id)
        if not order_data:
            logger.warning(f"找不到订单信息: {order_id}")
            return
            
        level_id = order_data["level_id"]
        side = order_data["side"]
        
        # 更新订单状态
        order_data["status"] = "canceled"
        order_data["cancel_time"] = time.time()
        self.order_manager.update_order(order_id, order_data)
        
        # 更新网格级别状态
        level = next((l for l in self.grid_levels_data if l.id == level_id), None)
        if not level:
            logger.warning(f"找不到网格级别: {level_id}")
            return
            
        if side == "buy":
            level.buy_order_id = None
            if level.status == "BUYING":
                level.status = "READY"
        else:  # sell
            level.sell_order_id = None
            if level.status == "SELLING":
                level.status = "BOUGHT"  # 重置为已买入状态
                
        logger.info(f"订单 {order_id} 已取消")
    
    async def cancel_all_orders(self):
        """取消所有活跃订单"""
        # 获取所有活跃订单ID
        active_order_ids = []
        for level in self.grid_levels_data:
            if level.buy_order_id:
                active_order_ids.append(level.buy_order_id)
            if level.sell_order_id:
                active_order_ids.append(level.sell_order_id)
        
        if not active_order_ids:
            return
            
        logger.info(f"取消所有活跃订单，共 {len(active_order_ids)} 个")
        
        # 批量取消订单
        for order_id in active_order_ids:
            try:
                await self.primary_exchange.cancel_order(order_id, self.trading_pair)
                logger.info(f"已取消订单: {order_id}")
            except Exception as e:
                logger.error(f"取消订单 {order_id} 失败: {e}")
    
    async def calculate_profit(self):
        """计算当前收益"""
        # 从交易记录中计算收益
        trades = self.trade_recorder.get_trades_by_strategy(self.strategy_id)
        
        buy_volume = Decimal("0")
        sell_volume = Decimal("0")
        buy_cost = Decimal("0")
        sell_revenue = Decimal("0")
        
        # 确保 trades 是一个列表
        if asyncio.iscoroutine(trades):
            trades = await trades

        for trade in trades:
            side = trade.get("side")
            price = Decimal(str(trade.get("price", "0")))
            amount = Decimal(str(trade.get("amount", "0")))
            
            if side == "buy":
                buy_volume += amount
                buy_cost += amount * price
            else:  # sell
                sell_volume += amount
                sell_revenue += amount * price
        
        # 计算已实现收益
        if sell_revenue > Decimal("0"):
            realized_profit = sell_revenue - buy_cost * (sell_volume / buy_volume) if buy_volume > 0 else 0
            self.total_profit = realized_profit
            
            logger.info(f"当前已实现收益: {realized_profit}")
        
        return self.total_profit
    
    async def check_risk_controls(self, current_price):
        """检查风险控制条件"""
        # 检查价格偏离
        if self.start_price > 0:
            price_deviation = abs(current_price - self.start_price) / self.start_price
            if price_deviation > self.max_price_deviation:
                logger.warning(f"价格偏离过大: {price_deviation:.2%}，超过设定阈值 {self.max_price_deviation:.2%}")
                # 可以添加告警或其他处理
        
        # 检查止损条件
        # (这里需要根据具体业务逻辑实现)
    
    async def get_current_price(self) -> Decimal:
        """获取当前交易对价格"""
        try:
            ticker = await self.primary_exchange.fetch_ticker(self.trading_pair)
            return Decimal(str(ticker["last"]))
        except Exception as e:
            logger.error(f"获取价格失败: {e}")
            # 返回上次有效价格或估算值
            if self.grid_levels_data and len(self.grid_levels_data) > 0:
                return (self.start_price + self.end_price) / 2
            return Decimal("0")
    
    async def get_exchange_precision(self) -> Tuple[Decimal, Decimal]:
        """获取交易所对当前交易对的精度要求"""
        try:
            market = await self.primary_exchange.load_market(self.trading_pair)
            
            price_precision_val = market.get("precision", {}).get("price")
            amount_precision_val = market.get("precision", {}).get("amount")

            if price_precision_val is None or amount_precision_val is None:
                logger.error(f"无法从交易所获取精度信息: price={price_precision_val}, amount={amount_precision_val}")
                # 提供一个默认的高精度值，避免程序崩溃
                return (Decimal("0.00000001"), Decimal("0.00000001"))

            return (Decimal(str(price_precision_val)), Decimal(str(amount_precision_val)))
        except Exception as e:
            logger.error(f"获取交易所精度时发生未知错误: {e}", exc_info=True)
            # 异常情况下也返回默认值
            return (Decimal("0.00000001"), Decimal("0.00000001"))
    
    def save_state(self):
        """保存当前策略状态"""
        state = {
            "strategy_id": self.strategy_id,
            "trading_pair": self.trading_pair,
            "start_price": str(self.start_price),
            "end_price": str(self.end_price),
            "total_investment": str(self.total_investment),
            "grid_levels": [level.to_dict() for level in self.grid_levels_data],
            "total_profit": str(self.total_profit),
            "completed_trades": self.completed_trades,
            "start_time": self.start_time,
            "last_update": time.time(),
            "orders": self.order_manager.get_all_orders()
        }
        
        self.state_manager.save_grid_state(self.strategy_id, state)
    
    def _restore_state(self, state):
        """从保存的状态恢复"""
        try:
            # 恢复基本参数
            self.trading_pair = state.get("trading_pair", self.trading_pair)
            self.start_price = Decimal(state.get("start_price", self.start_price))
            self.end_price = Decimal(state.get("end_price", self.end_price))
            self.total_investment = Decimal(state.get("total_investment", self.total_investment))
            
            # 恢复统计数据
            self.total_profit = Decimal(state.get("total_profit", "0"))
            self.completed_trades = state.get("completed_trades", 0)
            self.start_time = state.get("start_time", time.time())
            
            # 恢复网格级别
            grid_levels = state.get("grid_levels", [])
            self.grid_levels_data = [GridLevel.from_dict(level_data) for level_data in grid_levels]
            
            # 恢复订单管理器
            orders = state.get("orders", {})
            self.order_manager = OrderManager()
            for order_id, order_data in orders.items():
                self.order_manager.add_order(order_id, order_data)
                
            logger.info(f"已恢复策略 {self.strategy_id} 状态，{len(self.grid_levels_data)} 个网格点位")
            
        except Exception as e:
            logger.error(f"恢复状态失败: {e}")
    
    def _adjust_to_precision(self, value: Decimal, precision: Decimal) -> Decimal:
        """
        将数值调整到指定的精度，增加健壮性检查
        
        Args:
            value: 要调整的值
            precision: 精度
        
        Returns:
            调整后的值
        """
        if not isinstance(value, Decimal) or not isinstance(precision, Decimal):
            logger.error(f"调整精度失败：无效的输入类型 value: {type(value)}, precision: {type(precision)}")
            raise TypeError("Value and precision must be Decimal objects.")
        
        if precision <= 0:
            logger.error(f"调整精度失败：无效的精度值 {precision}")
            # 返回原始值或根据业务逻辑处理
            return value
            
        return (value / precision).quantize(Decimal('1'), rounding=ROUND_DOWN) * precision
    
    def get_status(self):
        """获取策略状态信息"""
        current_time = time.time()
        
        return {
            "strategy_id": self.strategy_id,
            "trading_pair": self.trading_pair,
            "start_price": str(self.start_price),
            "end_price": str(self.end_price),
            "grid_levels": len(self.grid_levels_data),
            "total_investment": str(self.total_investment),
            "total_profit": str(self.total_profit),
            "completed_trades": self.completed_trades,
            "running_time": current_time - self.start_time,
            "active_orders": self.order_manager.count_active_orders(),
            "last_update": time.ctime(current_time)
        }

    async def shutdown(self):
        """关闭策略，取消所有挂单"""
        logger.info(f"正在关闭策略 {self.strategy_id}...")
        try:
            await self.cancel_all_orders()
            logger.info(f"策略 {self.strategy_id} 已成功关闭，所有订单已取消。")
        except Exception as e:
            logger.error(f"关闭策略 {self.strategy_id} 时取消订单失败: {e}", exc_info=True)