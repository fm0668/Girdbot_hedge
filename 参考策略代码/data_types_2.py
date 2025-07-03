from decimal import Decimal  # 导入Decimal类，用于精确的小数计算
from enum import Enum  # 导入枚举类型
from typing import Literal, Optional  # 导入类型提示模块

from pydantic import BaseModel, ConfigDict  # 导入pydantic模型和配置字典

from hummingbot.core.data_type.common import OrderType, TradeType  # 导入订单类型和交易类型
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase  # 导入执行器配置基类
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig  # 导入三重障碍配置
from hummingbot.strategy_v2.models.executors import TrackedOrder  # 导入跟踪订单类型


class GridExecutorConfig(ExecutorConfigBase):
    """
    网格执行器配置类，定义了网格交易策略所需的所有参数
    """
    type: Literal["grid_executor"] = "grid_executor"  # 执行器类型，固定为grid_executor
    # Boundaries 边界设置
    connector_name: str  # 连接器名称，如交易所名称
    trading_pair: str  # 交易对，如BTC-USDT
    start_price: Decimal  # 网格起始价格
    end_price: Decimal  # 网格结束价格
    limit_price: Decimal  # 限制价格，用于风险控制
    side: TradeType = TradeType.BUY  # 交易方向，默认为买入
    # Profiling 性能配置
    total_amount_quote: Decimal  # 总报价金额（如USDT总量）
    min_spread_between_orders: Decimal = Decimal("0.0005")  # 订单之间的最小价差，默认为0.0005
    min_order_amount_quote: Decimal = Decimal("5")  # 最小订单报价金额，默认为5
    # Execution 执行配置
    max_open_orders: int = 5  # 最大开放订单数，默认为5
    max_orders_per_batch: Optional[int] = None  # 每批最大订单数，默认为None
    order_frequency: int = 0  # 订单频率，默认为0
    activation_bounds: Optional[Decimal] = None  # 激活边界，默认为None
    safe_extra_spread: Decimal = Decimal("0.0001")  # 安全额外价差，默认为0.0001
    # Risk Management 风险管理
    triple_barrier_config: TripleBarrierConfig  # 三重障碍配置，用于风险管理
    leverage: int = 20  # 杠杆倍数，默认为20倍
    level_id: Optional[str] = None  # 级别ID，默认为None
    deduct_base_fees: bool = False  # 是否扣除基础费用，默认为False
    keep_position: bool = False  # 是否保持仓位，默认为False
    coerce_tp_to_step: bool = True  # 是否将止盈价格强制调整为步长，默认为True
    # Hedge Mode 对冲模式配置
    hedge_mode: bool = False  # 是否启用对冲模式，默认为False
    hedge_connector_name: Optional[str] = None  # 对冲网格使用的连接器名称
    primary_account: Optional[str] = None  # 主账号标识
    hedge_account: Optional[str] = None  # 对冲账号标识
    is_primary: bool = True  # 是否为主网格
    hedge_executor_id: Optional[str] = None  # 对冲执行器ID
    # 预计算网格参数
    n_levels: Optional[int] = None  # 预计算的网格数量
    quote_amount_per_level: Optional[Decimal] = None  # 预计算的每个网格报价金额

    def create_hedge_config(self) -> 'GridExecutorConfig':
        """
        根据当前配置创建对冲网格配置（反方向配置）
        
        :return: 对冲网格执行器配置
        """
        # 创建新配置，复制当前配置但反转方向
        hedge_config = GridExecutorConfig(
            connector_name=self.hedge_connector_name,  # 使用对冲连接器
            trading_pair=self.trading_pair,  # 相同交易对
            start_price=self.end_price,  # 反转：开始价格为原结束价格
            end_price=self.start_price,  # 反转：结束价格为原开始价格
            limit_price=self.limit_price,  # 相同限制价格
            side=TradeType.SELL if self.side == TradeType.BUY else TradeType.BUY,  # 反转交易方向
            total_amount_quote=self.total_amount_quote,  # 相同总金额
            min_spread_between_orders=self.min_spread_between_orders,  # 相同最小价差
            min_order_amount_quote=self.min_order_amount_quote,  # 相同最小订单金额
            max_open_orders=self.max_open_orders,  # 相同最大开放订单数
            max_orders_per_batch=self.max_orders_per_batch,  # 相同每批最大订单数
            order_frequency=self.order_frequency,  # 相同订单频率
            activation_bounds=self.activation_bounds,  # 相同激活边界
            safe_extra_spread=self.safe_extra_spread,  # 相同安全额外价差
            triple_barrier_config=self.triple_barrier_config,  # 相同三重障碍配置
            leverage=self.leverage,  # 相同杠杆倍数
            level_id=self.level_id,  # 相同级别ID
            deduct_base_fees=self.deduct_base_fees,  # 相同费用扣除设置
            keep_position=self.keep_position,  # 相同保持仓位设置
            coerce_tp_to_step=True,  # 强制将止盈调整为步长
            hedge_mode=True,  # 启用对冲模式
            hedge_connector_name=self.connector_name,  # 对冲连接器为原始连接器
            primary_account=self.primary_account,  # 相同主账号标识
            hedge_account=self.hedge_account,  # 相同对冲账号标识
            is_primary=False,  # 标记为非主网格
            hedge_executor_id=self.id  # 对冲执行器ID为当前执行器ID
        )
        return hedge_config


class GridLevelStates(Enum):
    """
    网格级别状态枚举，表示网格中每个价格级别的当前状态
    """
    NOT_ACTIVE = "NOT_ACTIVE"  # 未激活
    OPEN_ORDER_PLACED = "OPEN_ORDER_PLACED"  # 已下开仓订单
    OPEN_ORDER_FILLED = "OPEN_ORDER_FILLED"  # 开仓订单已成交
    CLOSE_ORDER_PLACED = "CLOSE_ORDER_PLACED"  # 已下平仓订单
    COMPLETE = "COMPLETE"  # 完成（开仓和平仓都已完成）


class GridLevel(BaseModel):
    """
    网格级别类，表示网格中的一个价格级别
    """
    id: str  # 级别唯一标识符
    price: Decimal  # 此级别的价格
    amount_quote: Decimal  # 此级别的报价金额（如USDT金额）
    take_profit: Decimal  # 止盈比例或价格
    side: TradeType  # 交易方向（买入或卖出）
    open_order_type: OrderType  # 开仓订单类型
    take_profit_order_type: OrderType  # 止盈订单类型
    active_open_order: Optional[TrackedOrder] = None  # 当前活跃的开仓订单，默认为None
    active_close_order: Optional[TrackedOrder] = None  # 当前活跃的平仓订单，默认为None
    state: GridLevelStates = GridLevelStates.NOT_ACTIVE  # 级别状态，默认为未激活
    model_config = ConfigDict(arbitrary_types_allowed=True)  # 模型配置，允许任意类型

    def update_state(self):
        """
        更新网格级别的状态，根据开仓和平仓订单的状态
        """
        if self.active_open_order is None:
            self.state = GridLevelStates.NOT_ACTIVE  # 如果没有活跃的开仓订单，则状态为未激活
        elif self.active_open_order.is_filled:
            self.state = GridLevelStates.OPEN_ORDER_FILLED  # 如果开仓订单已成交，则状态为开仓订单已成交
        else:
            self.state = GridLevelStates.OPEN_ORDER_PLACED  # 否则状态为已下开仓订单
        if self.active_close_order is not None:
            if self.active_close_order.is_filled:
                self.state = GridLevelStates.COMPLETE  # 如果平仓订单已成交，则状态为完成
            else:
                self.state = GridLevelStates.CLOSE_ORDER_PLACED  # 否则状态为已下平仓订单

    def reset_open_order(self):
        """
        重置开仓订单，清除开仓订单并将状态设为未激活
        """
        self.active_open_order = None
        self.state = GridLevelStates.NOT_ACTIVE

    def reset_close_order(self):
        """
        重置平仓订单，清除平仓订单并将状态设为开仓订单已成交
        """
        self.active_close_order = None
        self.state = GridLevelStates.OPEN_ORDER_FILLED

    def reset_level(self):
        """
        重置整个级别，清除所有订单并将状态设为未激活
        """
        self.active_open_order = None
        self.active_close_order = None
        self.state = GridLevelStates.NOT_ACTIVE
