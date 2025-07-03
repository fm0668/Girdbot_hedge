"""
交易所管理器 - 管理多个交易所连接
"""
import asyncio
from typing import Dict, List, Optional, Union, Any

from girdbot.exchange.exchange_base import ExchangeBase
from girdbot.exchange.binance_spot import BinanceSpotExchange
from girdbot.exchange.binance_future import BinanceFutureExchange
from girdbot.utils.logger import get_logger

logger = get_logger("exchange_manager")

class ExchangeManager:
    """交易所管理器，负责管理多个交易所连接"""
    
    def __init__(self, exchange_configs: List[Dict[str, Any]]):
        """
        初始化交易所管理器
        
        Args:
            exchange_configs: 交易所配置列表
        """
        self.exchange_configs = exchange_configs
        self.exchanges: Dict[str, ExchangeBase] = {}
        self.primary_exchange: Optional[ExchangeBase] = None
    
    async def initialize(self):
        """
        初始化所有交易所连接
        """
        logger.info(f"初始化 {len(self.exchange_configs)} 个交易所连接")
        
        for config in self.exchange_configs:
            exchange = None
            try:
                # 提取配置
                name = config.get('name')
                api_key = config.get('api_key')
                api_secret = config.get('api_secret')
                account_alias = config.get('account_alias')
                is_primary = config.get('is_primary', False)
                testnet = config.get('testnet', False)
                
                # 检查必要参数
                if not name or not api_key or not api_secret:
                    logger.warning(f"交易所配置缺少必要参数: {config}")
                    continue
                
                # 创建交易所实例
                if name == 'binance':
                    exchange = BinanceSpotExchange(api_key, api_secret, account_alias, testnet)
                elif name == 'binance_future':
                    exchange = BinanceFutureExchange(api_key, api_secret, account_alias, testnet)
                else:
                    logger.warning(f"不支持的交易所类型: {name}")
                    continue
                
                # 初始化交易所
                await exchange.initialize()
                
                # 添加到管理器
                exchange_id = exchange.id
                self.exchanges[exchange_id] = exchange
                
                # 设置主交易所
                if is_primary:
                    self.primary_exchange = exchange
                    logger.info(f"设置 {exchange_id} 为主交易所")
                
                logger.info(f"交易所 {exchange_id} 初始化完成")
                
            except Exception as e:
                logger.error(f"初始化交易所失败: {e}")
                if exchange:
                    try:
                        await exchange.close()
                        logger.info(f"已关闭初始化失败的交易所连接: {exchange.id}")
                    except Exception as close_exc:
                        logger.error(f"关闭初始化失败的交易所 {getattr(exchange, 'id', 'N/A')} 时出错: {close_exc}")
        
        if not self.primary_exchange and self.exchanges:
            # 如果没有明确指定主交易所，使用第一个作为主交易所
            first_exchange_id = list(self.exchanges.keys())[0]
            self.primary_exchange = self.exchanges[first_exchange_id]
            logger.info(f"未指定主交易所，使用 {first_exchange_id} 作为主交易所")
        
        logger.info(f"交易所管理器初始化完成，共 {len(self.exchanges)} 个交易所连接")
    
    async def close(self):
        """
        关闭所有交易所连接
        """
        close_tasks = []
        for exchange_id, exchange in self.exchanges.items():
            try:
                task = asyncio.create_task(exchange.close())
                close_tasks.append(task)
                logger.info(f"正在关闭交易所 {exchange_id} 连接...")
            except Exception as e:
                logger.error(f"关闭交易所 {exchange_id} 连接时出错: {e}")
        
        if close_tasks:
            try:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"关闭交易所连接时出错: {e}")
        
        # 等待所有可能的异步任务完成
        await asyncio.sleep(0.5)  # 给异步任务一些时间完成
        
        # 确保所有与交易所相关的任务都已完成
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            relevant_tasks = []
            for task in tasks:
                task_name = task.get_name()
                # 只等待与交易所相关的任务
                if "exchange" in task_name.lower() or "binance" in task_name.lower() or "ccxt" in task_name.lower():
                    relevant_tasks.append(task)
            
            if relevant_tasks:
                logger.info(f"等待 {len(relevant_tasks)} 个交易所相关任务完成...")
                try:
                    await asyncio.wait_for(asyncio.gather(*relevant_tasks, return_exceptions=True), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("等待交易所任务超时，部分资源可能未正确释放")
            
        logger.info("所有交易所连接已关闭")
    
    def get_exchange(self, exchange_id: str) -> Optional[ExchangeBase]:
        """
        获取指定ID的交易所实例
        
        Args:
            exchange_id: 交易所ID
            
        Returns:
            交易所实例或None
        """
        return self.exchanges.get(exchange_id)
    
    def get_exchange_by_name(self, exchange_name: str) -> Optional[ExchangeBase]:
        """
        获取指定名称的交易所实例
        
        Args:
            exchange_name: 交易所名称
            
        Returns:
            交易所实例或None
        """
        for exchange in self.exchanges.values():
            if exchange.name == exchange_name:
                return exchange
        return None
    
    def get_primary_exchange(self) -> Optional[ExchangeBase]:
        """
        获取主交易所实例
        
        Returns:
            主交易所实例或None
        """
        return self.primary_exchange
    
    def get_hedge_exchanges(self) -> List[ExchangeBase]:
        """
        获取对冲交易所列表
        
        Returns:
            对冲交易所实例列表
        """
        # 对冲交易所是那些配置中标记为is_hedge=True的交易所
        hedge_exchanges = []
        for config in self.exchange_configs:
            is_hedge = config.get('is_hedge', False)
            account_alias = config.get('account_alias')
            
            if is_hedge and account_alias:
                exchange_id = f"{config.get('name')}_{account_alias}"
                exchange = self.exchanges.get(exchange_id)
                if exchange:
                    hedge_exchanges.append(exchange)
        
        return hedge_exchanges
    
    def get_all_exchanges(self) -> List[ExchangeBase]:
        """
        获取所有交易所实例
        
        Returns:
            所有交易所实例列表
        """
        return list(self.exchanges.values())
    
    async def check_connections(self) -> Dict[str, bool]:
        """
        检查所有交易所连接状态
        
        Returns:
            交易所ID -> 连接状态的字典
        """
        result = {}
        check_tasks = {}
        
        # 创建所有检查任务
        for exchange_id, exchange in self.exchanges.items():
            check_tasks[exchange_id] = exchange.ping()
        
        # 并行执行所有检查任务
        for exchange_id, task in check_tasks.items():
            try:
                result[exchange_id] = await task
            except Exception:
                result[exchange_id] = False
                
        return result
    
    async def fetch_all_balances(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有交易所的余额
        
        Returns:
            交易所ID -> 余额信息的字典
        """
        results = {}
        balance_tasks = {}
        
        # 创建所有余额查询任务
        for exchange_id, exchange in self.exchanges.items():
            balance_tasks[exchange_id] = exchange.fetch_balance()
        
        # 并行执行所有查询任务
        for exchange_id, task in balance_tasks.items():
            try:
                results[exchange_id] = await task
            except Exception as e:
                logger.error(f"获取交易所 {exchange_id} 余额失败: {e}")
                results[exchange_id] = {"error": str(e)}
                
        return results
    
    def get_exchange_by_alias(self, account_alias: str) -> Optional[ExchangeBase]:
        """
        通过账户别名获取交易所实例
        
        Args:
            account_alias: 账户别名
            
        Returns:
            交易所实例或None
        """
        for exchange in self.exchanges.values():
            if exchange.account_alias == account_alias:
                return exchange
        return None
    
    def get_exchange_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有交易所的状态信息
        
        Returns:
            交易所状态信息字典
        """
        status = {}
        for exchange_id, exchange in self.exchanges.items():
            status[exchange_id] = {
                "name": exchange.name,
                "account_alias": exchange.account_alias,
                "initialized": exchange.initialized,
                "is_primary": exchange == self.primary_exchange,
                "is_hedge": exchange.account_alias is not None and exchange in self.get_hedge_exchanges()
            }
        return status
    
    async def refresh_markets(self):
        """
        刷新所有交易所的市场信息
        """
        refresh_tasks = []
        for exchange in self.exchanges.values():
            # 假设交易所实例有refresh_markets方法，如果没有可以移除此功能
            if hasattr(exchange, 'refresh_markets'):
                refresh_tasks.append(exchange.refresh_markets())
            # 或者使用通用方法
            elif hasattr(exchange.exchange, 'load_markets'):
                refresh_tasks.append(exchange.exchange.load_markets(reload=True))
        
        if refresh_tasks:
            await asyncio.gather(*refresh_tasks, return_exceptions=True)
            logger.info("所有交易所市场信息已刷新")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将交易所管理器状态转换为字典
        
        Returns:
            状态字典
        """
        return {
            "exchanges_count": len(self.exchanges),
            "primary_exchange": self.primary_exchange.id if self.primary_exchange else None,
            "exchanges": [
                {
                    "id": exchange.id,
                    "name": exchange.name,
                    "account_alias": exchange.account_alias,
                    "initialized": exchange.initialized,
                    "is_primary": exchange == self.primary_exchange,
                    "symbols_count": len(exchange.symbols) if hasattr(exchange, "symbols") else 0
                } for exchange in self.exchanges.values()
            ]
        }