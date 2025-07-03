"""
API路由 - 定义Web服务的API路由
"""
import json
import time
from typing import Dict, Any, List

from aiohttp import web

from girdbot.utils.logger import get_logger

logger = get_logger("web_routes")

def setup_routes(app: web.Application, engine) -> None:
    """
    设置API路由
    
    Args:
        app: Web应用实例
        engine: 网格引擎实例
    """
    # 存储引擎引用，供路由处理函数使用
    app["engine"] = engine
    
    # 添加路由
    app.router.add_get('/', index_handler)
    app.router.add_get('/api/status', status_handler)
    app.router.add_get('/api/grids', grids_handler)
    app.router.add_get('/api/trades', trades_handler)
    app.router.add_get('/api/stats', stats_handler)

async def index_handler(request: web.Request) -> web.Response:
    """首页处理"""
    index_path = request.app.router['static'].get_info()['directory'] + '/index.html'
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return web.Response(text=content, content_type='text/html')

async def status_handler(request: web.Request) -> web.Response:
    """系统状态API"""
    engine = request.app["engine"]
    
    status = {
        "status": "running" if engine.is_running else "stopped",
        "uptime": int(time.time() - engine.start_time),
        "version": engine.version,
        "exchange_count": len(engine.exchange_manager.exchanges),
        "grid_count": len(engine.grid_strategies),
    }
    
    return web.json_response(status)

async def grids_handler(request: web.Request) -> web.Response:
    """网格策略状态API"""
    engine = request.app["engine"]
    
    grid_id = request.query.get('id')
    if grid_id and grid_id in engine.grid_strategies:
        # 返回单个网格状态
        strategy = engine.grid_strategies[grid_id]
        return web.json_response(strategy.get_status())
    
    # 返回所有网格状态摘要
    grids = []
    for grid_id, strategy in engine.grid_strategies.items():
        grids.append(strategy.get_status(detailed=False))
    
    return web.json_response({"grids": grids})

async def trades_handler(request: web.Request) -> web.Response:
    """交易记录API"""
    engine = request.app["engine"]
    
    grid_id = request.query.get('grid_id')
    limit = int(request.query.get('limit', 20))
    
    trades = await engine.trade_recorder.get_recent_trades(grid_id, limit)
    return web.json_response({"trades": trades})

async def stats_handler(request: web.Request) -> web.Response:
    """统计数据API"""
    engine = request.app["engine"]
    
    grid_id = request.query.get('grid_id')
    
    if grid_id and grid_id in engine.grid_strategies:
        # 返回单个网格统计
        strategy = engine.grid_strategies[grid_id]
        stats = strategy.get_stats()
    else:
        # 返回全局统计
        stats = {
            "total_profit": sum(s.get_stats()["total_profit"] for s in engine.grid_strategies.values()),
            "total_trades": sum(s.get_stats()["total_trades"] for s in engine.grid_strategies.values()),
            "active_orders": sum(s.get_stats()["active_orders"] for s in engine.grid_strategies.values()),
            "filled_orders": sum(s.get_stats()["filled_orders"] for s in engine.grid_strategies.values()),
        }
    
    return web.json_response(stats)