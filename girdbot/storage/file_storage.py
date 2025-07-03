"""
文件存储实现 - 提供基础的文件操作功能
"""
import os
import json
import time
import shutil
import asyncio
from typing import Dict, Any, Optional
import aiofiles
from girdbot.utils.logger import get_logger

logger = get_logger("file_storage")

class FileStorage:
    """文件存储类，处理JSON文件的读写操作"""
    
    def __init__(self, data_dir: str = "./data"):
        """
        初始化文件存储
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self._ensure_directory()
        
        # 文件操作锁，防止并发写入冲突
        self._file_locks: Dict[str, asyncio.Lock] = {}
        
    def _ensure_directory(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)
        
    def get_file_path(self, filename: str) -> str:
        """
        获取文件的完整路径
        
        Args:
            filename: 文件名
            
        Returns:
            文件的完整路径
        """
        return os.path.join(self.data_dir, filename)
    
    async def save_json(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        将数据保存为JSON文件
        
        Args:
            filename: 文件名
            data: 要保存的数据
            
        Returns:
            是否成功保存
        """
        file_path = self.get_file_path(filename)
        temp_file = f"{file_path}.tmp"
        
        # 获取或创建文件锁
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
            
        async with self._file_locks[file_path]:
            try:
                # 先写入临时文件
                async with aiofiles.open(temp_file, 'w') as f:
                    await f.write(json.dumps(data, indent=2, default=str))
                
                # 然后原子地重命名替换原文件
                shutil.move(temp_file, file_path)
                return True
            except Exception as e:
                logger.error(f"保存JSON文件 {filename} 失败: {e}")
                # 清理临时文件
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                return False
    
    async def load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        从JSON文件加载数据
        
        Args:
            filename: 文件名
            
        Returns:
            加载的数据或None
        """
        file_path = self.get_file_path(filename)
        
        if not os.path.exists(file_path):
            return None
            
        # 获取或创建文件锁
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
            
        async with self._file_locks[file_path]:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            except Exception as e:
                logger.error(f"加载JSON文件 {filename} 失败: {e}")
                return None
    
    def load_json_sync(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        同步从JSON文件加载数据
        
        Args:
            filename: 文件名
            
        Returns:
            加载的数据或None
        """
        file_path = self.get_file_path(filename)
        
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"同步加载JSON文件 {filename} 失败: {e}")
            return None
    
    def save_json_sync(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        同步将数据保存为JSON文件
        
        Args:
            filename: 文件名
            data: 要保存的数据
            
        Returns:
            是否成功保存
        """
        file_path = self.get_file_path(filename)
        temp_file = f"{file_path}.tmp"
        
        try:
            # 先写入临时文件
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # 然后原子地重命名替换原文件
            shutil.move(temp_file, file_path)
            return True
        except Exception as e:
            logger.error(f"同步保存JSON文件 {filename} 失败: {e}")
            # 清理临时文件
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return False
    
    def list_files(self, pattern: str = None) -> list:
        """
        列出目录中的文件
        
        Args:
            pattern: 文件名模式(可选)
            
        Returns:
            文件名列表
        """
        try:
            files = os.listdir(self.data_dir)
            if pattern:
                import fnmatch
                files = [f for f in files if fnmatch.fnmatch(f, pattern)]
            return files
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return []
    
    def file_exists(self, filename: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            filename: 文件名
            
        Returns:
            文件是否存在
        """
        file_path = self.get_file_path(filename)
        return os.path.exists(file_path)
    
    def backup_file(self, filename: str) -> bool:
        """
        备份文件
        
        Args:
            filename: 文件名
            
        Returns:
            是否成功备份
        """
        if not self.file_exists(filename):
            return False
            
        source_path = self.get_file_path(filename)
        timestamp = int(time.time())
        backup_name = f"{filename}.backup.{timestamp}"
        backup_path = self.get_file_path(backup_name)
        
        try:
            shutil.copy2(source_path, backup_path)
            return True
        except Exception as e:
            logger.error(f"备份文件 {filename} 失败: {e}")
            return False
    
    def delete_file(self, filename: str) -> bool:
        """
        删除文件
        
        Args:
            filename: 文件名
            
        Returns:
            是否成功删除
        """
        file_path = self.get_file_path(filename)
        
        if not os.path.exists(file_path):
            return True
            
        try:
            os.unlink(file_path)
            return True
        except Exception as e:
            logger.error(f"删除文件 {filename} 失败: {e}")
            return False