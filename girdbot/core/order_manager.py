"""
订单管理器 - 管理交易订单
"""
import time
from typing import Dict, List, Optional

class OrderManager:
    """订单管理器，负责管理和跟踪所有交易订单"""
    
    def __init__(self):
        """初始化订单管理器"""
        self.orders: Dict[str, Dict] = {}  # 订单ID -> 订单信息
    
    def add_order(self, order_id: str, order_data: Dict) -> bool:
        """
        添加订单
        
        Args:
            order_id: 订单ID
            order_data: 订单数据
            
        Returns:
            是否成功添加
        """
        if order_id in self.orders:
            return False
            
        self.orders[order_id] = order_data
        return True
    
    def update_order(self, order_id: str, order_data: Dict) -> bool:
        """
        更新订单信息
        
        Args:
            order_id: 订单ID
            order_data: 新的订单数据
            
        Returns:
            是否成功更新
        """
        if order_id not in self.orders:
            return False
            
        self.orders[order_id] = order_data
        return True
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单信息或None
        """
        return self.orders.get(order_id)
    
    def delete_order(self, order_id: str) -> bool:
        """
        删除订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否成功删除
        """
        if order_id not in self.orders:
            return False
            
        del self.orders[order_id]
        return True
    
    def get_all_orders(self) -> Dict[str, Dict]:
        """
        获取所有订单
        
        Returns:
            所有订单的字典
        """
        return self.orders
    
    def get_orders_by_status(self, status: str) -> List[Dict]:
        """
        获取指定状态的订单
        
        Args:
            status: 订单状态，如 'open', 'filled', 'canceled', 'failed'
            
        Returns:
            订单列表
        """
        return [
            {"id": order_id, **order_data}
            for order_id, order_data in self.orders.items()
            if order_data.get("status") == status
        ]
    
    def get_orders_by_side(self, side: str) -> List[Dict]:
        """
        获取指定交易方向的订单
        
        Args:
            side: 交易方向，'buy' 或 'sell'
            
        Returns:
            订单列表
        """
        return [
            {"id": order_id, **order_data}
            for order_id, order_data in self.orders.items()
            if order_data.get("side") == side
        ]
    
    def get_active_orders(self) -> List[Dict]:
        """
        获取所有活跃订单（未成交、未取消）
        
        Returns:
            活跃订单列表
        """
        return [
            {"id": order_id, **order_data}
            for order_id, order_data in self.orders.items()
            if order_data.get("status") in ["open", "partially_filled"]
        ]
    
    def count_active_orders(self) -> int:
        """
        计算活跃订单数量
        
        Returns:
            活跃订单数量
        """
        return len([
            1 for order_data in self.orders.values()
            if order_data.get("status") in ["open", "partially_filled"]
        ])
    
    def get_orders_by_level_id(self, level_id: str) -> List[Dict]:
        """
        获取指定网格级别的订单
        
        Args:
            level_id: 网格级别ID
            
        Returns:
            订单列表
        """
        return [
            {"id": order_id, **order_data}
            for order_id, order_data in self.orders.items()
            if order_data.get("level_id") == level_id
        ]
    
    def get_orders_by_time_range(self, start_time: float, end_time: float) -> List[Dict]:
        """
        获取指定时间范围内创建的订单
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            订单列表
        """
        return [
            {"id": order_id, **order_data}
            for order_id, order_data in self.orders.items()
            if start_time <= order_data.get("timestamp", 0) <= end_time
        ]
    
    def clean_old_orders(self, max_age: float) -> int:
        """
        清理旧订单
        
        Args:
            max_age: 最大订单年龄（秒）
            
        Returns:
            清理的订单数量
        """
        current_time = time.time()
        old_orders = [
            order_id for order_id, order_data in self.orders.items()
            if (current_time - order_data.get("timestamp", 0)) > max_age
            and order_data.get("status") not in ["open", "partially_filled"]
        ]
        
        for order_id in old_orders:
            self.delete_order(order_id)
            
        return len(old_orders)
    
    def get_order_status_summary(self) -> Dict[str, int]:
        """
        获取订单状态汇总
        
        Returns:
            各状态订单数量的字典
        """
        summary = {}
        for order_data in self.orders.values():
            status = order_data.get("status", "unknown")
            summary[status] = summary.get(status, 0) + 1
            
        return summary
    
    def bulk_update_orders(self, updates: Dict[str, Dict]) -> int:
        """
        批量更新订单
        
        Args:
            updates: 订单ID -> 更新数据的字典
            
        Returns:
            成功更新的订单数量
        """
        updated_count = 0
        for order_id, update_data in updates.items():
            if self.update_order(order_id, update_data):
                updated_count += 1
                
        return updated_count
    
    def reset(self):
        """清空所有订单"""
        self.orders = {}