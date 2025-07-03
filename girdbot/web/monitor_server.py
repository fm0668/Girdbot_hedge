"""
Web服务器 - 实现简易的Web监控服务器
"""
import asyncio
import os
import json
from typing import Dict, Any, Optional

from aiohttp import web
import aiohttp_cors

from girdbot.utils.logger import get_logger
from girdbot.web.routes import setup_routes

logger = get_logger("web_monitor")

async def start_web_monitor(config: Dict[str, Any], engine) -> Optional[web.AppRunner]:
    """
    启动Web监控服务器
    
    Args:
        config: 系统配置
        engine: 网格引擎实例
    
    Returns:
        web.AppRunner实例或None(如果配置禁用了Web监控)
    """
    if not config.get("system", {}).get("enable_web_monitor", False):
        logger.info("Web监控功能已禁用")
        return None
    
    host = config.get("system", {}).get("web_host", "0.0.0.0")
    port = config.get("system", {}).get("web_port", 8080)
    
    app = web.Application()
    
    # 配置CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    # 设置静态文件路径
    static_path = os.path.join(os.path.dirname(__file__), "static")
    app.router.add_static('/static/', path=static_path, name='static')
    
    # 设置路由
    setup_routes(app, engine)
    
    # 应用CORS设置到所有路由
    for route in list(app.router.routes()):
        if not isinstance(route.resource, web.StaticResource):
            cors.add(route)
    
    # 启动服务器
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Web监控服务器已启动: http://{host}:{port}")
    return runner

async def stop_web_monitor(runner: Optional[web.AppRunner]):
    """
    停止Web监控服务器
    
    Args:
        runner: web.AppRunner实例
    """
    if runner:
        logger.info("正在关闭Web监控服务器...")
        await runner.cleanup()
        logger.info("Web监控服务器已关闭")