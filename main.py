#!/usr/bin/env python3
"""
Girdbot_hedge - 加密货币网格量化交易系统
主入口文件
"""
import asyncio
import os
import signal
import sys

from girdbot.core.engine import GridEngine
from girdbot.utils.config_loader import load_config
from girdbot.utils.logger import setup_logger

# 全局变量
engine = None
web_runner = None
logger = setup_logger()

async def main():
    """主程序入口"""
    logger.info("启动 Girdbot_hedge 网格量化交易系统...")
    
    try:
        # 加载配置
        config_path = os.environ.get("CONFIG_PATH", "config.yaml")
        config = load_config(config_path)
        if not config:
            logger.critical("无法加载配置文件，程序退出")
            return
        
        # 创建引擎实例
        global engine
        engine = GridEngine(config)
        
        # 初始化引擎
        init_success = await engine.initialize()
        if not init_success:
            logger.critical("引擎初始化失败，无法继续运行。请检查配置和交易所连接。")
            await engine.shutdown()  # 确保关闭引擎以释放资源
            return
        
        # 启动Web监控（如果配置中启用）
        global web_runner
        if config["system"].get("enable_web_monitor", False):
            from girdbot.web.monitor_server import start_web_monitor, stop_web_monitor
            web_runner = await start_web_monitor(config, engine)
        
        # 启动引擎
        await engine.start()
        
        # 保持程序运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭系统...")
    except Exception as e:
        logger.exception(f"程序出现未处理异常: {e}")
    finally:
        # 关闭Web服务器
        if web_runner:
            from girdbot.web.monitor_server import stop_web_monitor
            await stop_web_monitor(web_runner)
        
        # 关闭引擎
        if engine:
            await engine.shutdown()
            
        # 确保所有异步任务完成，但设置5秒超时
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            logger.info(f"等待 {len(tasks)} 个异步任务完成（最多5秒）...")
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5.0)
                logger.info("所有异步任务已完成")
            except asyncio.TimeoutError:
                logger.warning("等待异步任务超时，强制退出")
            
        logger.info("系统已关闭")

def signal_handler(sig, frame):
    """处理系统信号"""
    logger.info(f"接收到信号 {sig}，准备关闭...")
    if asyncio.get_event_loop().is_running():
        asyncio.create_task(shutdown())

async def shutdown():
    """关闭所有系统组件"""
    # 关闭Web服务器
    global web_runner
    if web_runner:
        from girdbot.web.monitor_server import stop_web_monitor
        await stop_web_monitor(web_runner)
    
    # 关闭引擎
    global engine
    if engine:
        await engine.shutdown()
    
    # 确保所有异步任务完成，但设置5秒超时
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        logger.info(f"等待 {len(tasks)} 个异步任务完成（最多5秒）...")
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5.0)
            logger.info("所有异步任务已完成")
        except asyncio.TimeoutError:
            logger.warning("等待异步任务超时，强制退出")

if __name__ == "__main__":
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行主程序
    asyncio.run(main())