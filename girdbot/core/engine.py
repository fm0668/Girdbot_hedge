"""
核心引擎 - 协调整个系统的运行
"""
import asyncio
import time
import uuid
from typing import Dict, List

from girdbot.core.grid_strategy import GridStrategy
from girdbot.core.hedge_manager import HedgeManager
from girdbot.exchange.exchange_manager import ExchangeManager
from girdbot.storage.grid_state import GridStateManager
from girdbot.storage.trade_recorder import TradeRecorder
from girdbot.utils.logger import get_logger

logger = get_logger("engine")

class GridEngine:
    """网格交易引擎，负责协调整个系统的运行"""
    
    def __init__(self, config: dict):
        """
        初始化网格交易引擎
        
        Args:
            config: 系统配置字典
        """
        self.config = config
        self.system_config = config["system"]
        self.data_dir = self.system_config.get("data_dir", "./data")
        self.update_interval = self.system_config.get("update_interval", 2)
        
        # 初始化组件
        self.exchange_manager = ExchangeManager(config["exchanges"])
        self.state_manager = GridStateManager(self.data_dir)
        self.trade_recorder = TradeRecorder(self.data_dir)
        self.hedge_manager = HedgeManager(self.exchange_manager)
        self.strategies: Dict[str, GridStrategy] = {}
        
        # 运行标志
        self.is_running = False
        self.tasks = []
    
    async def initialize(self):
        """初始化引擎"""
        logger.info("初始化网格交易引擎...")
        
        # 初始化交易所连接
        await self.exchange_manager.initialize()
        
        # 检查是否有可用的交易所连接
        if len(self.exchange_manager.exchanges) == 0:
            logger.error("没有可用的交易所连接，请检查API密钥和网络连接")
            return False
        
        # 初始化策略
        await self.initialize_strategies()
        
        logger.info("引擎初始化完成")
        return True
    
    async def initialize_strategies(self):
        """初始化所有配置的策略"""
        strategy_configs = self.config.get("strategies", [])
        if not strategy_configs:
            logger.warning("没有配置任何网格策略")
            return
            
        initialized_count = 0
        for strategy_config in strategy_configs:
            strategy_id = strategy_config["id"]
            logger.info(f"初始化策略: {strategy_id}")
            
            # 恢复策略状态(如果存在)
            saved_state = self.state_manager.load_grid_state(strategy_id)
            
            # 创建策略实例
            try:
                strategy = GridStrategy(
                    strategy_id=strategy_id,
                    config=strategy_config,
                    exchange_manager=self.exchange_manager,
                    state_manager=self.state_manager,
                    trade_recorder=self.trade_recorder,
                    hedge_manager=self.hedge_manager if strategy_config.get("enable_hedge", False) else None,
                    saved_state=saved_state
                )
                
                self.strategies[strategy_id] = strategy
                initialized_count += 1
            except Exception as e:
                logger.error(f"创建策略 {strategy_id} 实例失败: {e}")
                
        if initialized_count == 0 and len(strategy_configs) > 0:
            logger.error("所有策略初始化失败")
    
    async def start(self):
        """启动引擎和所有策略"""
        if self.is_running:
            logger.warning("引擎已经在运行中")
            return
            
        logger.info("启动网格交易引擎...")
        self.is_running = True
        
        # 启动所有策略
        for strategy_id, strategy in self.strategies.items():
            logger.info(f"启动策略: {strategy_id}")
            task = asyncio.create_task(self.run_strategy(strategy))
            self.tasks.append(task)
            
        # 启动状态更新任务
        status_task = asyncio.create_task(self.update_status_periodically())
        self.tasks.append(status_task)
        
        logger.info("所有策略已启动")
    
    async def run_strategy(self, strategy: GridStrategy):
        """
        运行单个策略
        
        Args:
            strategy: 策略实例
        """
        try:
            # 初始化策略
            init_success = await strategy.initialize()
            if not init_success:
                logger.error(f"策略 {strategy.strategy_id} 初始化失败，无法运行")
                return
                
            # 策略主循环
            while self.is_running:
                try:
                    await strategy.update()
                except Exception as e:
                    logger.error(f"策略 {strategy.strategy_id} 更新时出错: {e}", exc_info=True)
                
                await asyncio.sleep(self.update_interval)
                
        except Exception as e:
            logger.exception(f"策略 {strategy.strategy_id} 运行时发生异常: {e}")
            # 出现异常时尝试保存状态
            strategy.save_state()
    
    async def update_status_periodically(self):
        """定期更新和保存系统状态"""
        while self.is_running:
            try:
                # 更新系统状态
                status = self.get_system_status()
                
                # 保存到状态文件
                self.state_manager.save_system_status(status)
                
            except Exception as e:
                logger.error(f"更新系统状态时出错: {e}")
            
            await asyncio.sleep(30)  # 每30秒更新一次
    
    def get_system_status(self):
        """获取系统状态信息"""
        current_time = time.time()
        
        status = {
            "timestamp": current_time,
            "last_update": time.ctime(current_time),
            "uptime": current_time - self.state_manager.start_time,
            "strategies": []
        }
        
        # 收集所有策略状态
        for strategy_id, strategy in self.strategies.items():
            strategy_status = strategy.get_status()
            status["strategies"].append(strategy_status)
            
        return status
    
    async def shutdown(self):
        """关闭引擎和所有策略，确保所有资源被正确释放"""
        if not self.is_running:
            logger.info("引擎尚未运行，执行基本清理...")
            await self.exchange_manager.close()
            logger.info("交易所连接已关闭")
            return

        logger.info("正在关闭网格交易引擎...")
        self.is_running = False  # 停止所有策略循环

        # 1. 优雅地关闭所有策略（包括取消挂单和平仓）
        shutdown_tasks = []
        for strategy_id, strategy in self.strategies.items():
            logger.info(f"请求关闭策略: {strategy_id}")
            shutdown_tasks.append(asyncio.create_task(strategy.shutdown()))
        
        if shutdown_tasks:
            try:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
                logger.info("所有策略已关闭。")
            except Exception as e:
                logger.error(f"关闭策略时出错: {e}", exc_info=True)

        # 2. 取消引擎的后台任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        if self.tasks:
            try:
                await asyncio.gather(*self.tasks, return_exceptions=True)
                logger.info("所有引擎后台任务已取消。")
            except Exception as e:
                logger.error(f"取消后台任务时出错: {e}", exc_info=True)
        self.tasks = []

        # 3. 保存所有策略的最终状态
        for strategy_id, strategy in self.strategies.items():
            try:
                strategy.save_state()
                logger.info(f"策略 {strategy_id} 状态已保存")
            except Exception as e:
                logger.error(f"保存策略 {strategy_id} 最终状态时出错: {e}")
        
        # 4. 最后关闭交易所连接
        try:
            await self.exchange_manager.close()
            logger.info("所有交易所连接已关闭")
        except Exception as e:
            logger.error(f"关闭交易所连接时出错: {e}", exc_info=True)
        
        logger.info("引擎已成功关闭")
    
    def get_strategy(self, strategy_id):
        """获取指定ID的策略实例"""
        return self.strategies.get(strategy_id)
    
    def get_all_strategies(self):
        """获取所有策略实例"""
        return self.strategies