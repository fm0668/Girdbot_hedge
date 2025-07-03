"""
网格状态管理 - 负责网格策略状态的存储和恢复
"""
import os
import time
from typing import Dict, Any, Optional, List
import asyncio

from girdbot.storage.file_storage import FileStorage
from girdbot.utils.logger import get_logger

logger = get_logger("grid_state")

class GridStateManager:
    """
    网格状态管理器，处理网格策略状态的保存、加载和恢复
    """
    
    def __init__(self, data_dir: str = "./data"):
        """
        初始化网格状态管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.storage = FileStorage(os.path.join(data_dir, "grid_states"))
        self.start_time = time.time()
        self._last_save_time = {}
        self._save_interval = 5  # 状态保存最小间隔(秒)
    
    def save_grid_state(self, strategy_id: str, state: Dict[str, Any]) -> bool:
        """
        保存网格策略状态
        
        Args:
            strategy_id: 策略ID
            state: 策略状态数据
            
        Returns:
            是否成功保存
        """
        # 避免过于频繁的保存
        current_time = time.time()
        last_save = self._last_save_time.get(strategy_id, 0)
        
        if current_time - last_save < self._save_interval:
            return True
            
        filename = f"{strategy_id}.json"
        
        # 添加保存时间戳
        state_copy = state.copy()
        state_copy["_last_saved"] = current_time
        
        # 同步保存状态
        result = self.storage.save_json_sync(filename, state_copy)
        
        if result:
            self._last_save_time[strategy_id] = current_time
            logger.debug(f"保存网格状态: {strategy_id}")
            
        return result
    
    def load_grid_state(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        加载网格策略状态
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略状态数据或None
        """
        filename = f"{strategy_id}.json"
        
        # 同步加载状态
        state = self.storage.load_json_sync(filename)
        
        if state:
            logger.info(f"加载网格状态: {strategy_id}, 上次保存时间: {state.get('_last_saved', 'unknown')}")
        else:
            logger.info(f"未找到网格状态: {strategy_id}")
            
        return state
    
    def delete_grid_state(self, strategy_id: str) -> bool:
        """
        删除网格策略状态
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否成功删除
        """
        filename = f"{strategy_id}.json"
        
        if strategy_id in self._last_save_time:
            del self._last_save_time[strategy_id]
            
        result = self.storage.delete_file(filename)
        
        if result:
            logger.info(f"删除网格状态: {strategy_id}")
            
        return result
    
    def backup_grid_state(self, strategy_id: str) -> bool:
        """
        备份网格策略状态
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否成功备份
        """
        filename = f"{strategy_id}.json"
        result = self.storage.backup_file(filename)
        
        if result:
            logger.info(f"备份网格状态: {strategy_id}")
            
        return result
    
    def list_grid_states(self) -> List[str]:
        """
        列出所有保存的网格策略状态
        
        Returns:
            策略ID列表
        """
        files = self.storage.list_files("*.json")
        strategy_ids = [f.replace(".json", "") for f in files]
        return strategy_ids
    
    def get_all_grid_states(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有网格策略状态
        
        Returns:
            策略ID -> 状态数据的字典
        """
        strategy_ids = self.list_grid_states()
        states = {}
        
        for strategy_id in strategy_ids:
            state = self.load_grid_state(strategy_id)
            if state:
                states[strategy_id] = state
                
        return states
    
    def save_system_status(self, status: Dict[str, Any]) -> bool:
        """
        保存系统状态
        
        Args:
            status: 系统状态数据
            
        Returns:
            是否成功保存
        """
        return self.storage.save_json_sync("system_status.json", status)
    
    def load_system_status(self) -> Optional[Dict[str, Any]]:
        """
        加载系统状态
        
        Returns:
            系统状态数据或None
        """
        return self.storage.load_json_sync("system_status.json")
    
    async def auto_backup_states(self, interval: int = 3600):
        """
        定期自动备份所有网格状态
        
        Args:
            interval: 备份间隔(秒)
        """
        while True:
            try:
                # 获取所有策略ID
                strategy_ids = self.list_grid_states()
                
                for strategy_id in strategy_ids:
                    self.backup_grid_state(strategy_id)
                    
                # 备份系统状态
                system_status = self.load_system_status()
                if system_status:
                    self.storage.save_json_sync("system_status.backup.json", system_status)
                    
                logger.info(f"自动备份完成，备份了 {len(strategy_ids)} 个网格状态")
                    
            except Exception as e:
                logger.error(f"自动备份失败: {e}")
                
            await asyncio.sleep(interval)