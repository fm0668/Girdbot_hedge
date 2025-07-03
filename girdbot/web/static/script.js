// 全局变量
let refreshInterval = 5000; // 刷新间隔(毫秒)
let selectedGridId = null;
let refreshTimer = null;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', () => {
    // 初始化页面
    initPage();
    
    // 设置自动刷新
    refreshTimer = setInterval(refreshData, refreshInterval);
});

// 初始化页面
function initPage() {
    fetchSystemStatus();
    fetchStats();
    fetchGrids();
    fetchTrades();
}

// 刷新所有数据
function refreshData() {
    fetchSystemStatus();
    fetchStats();
    fetchGrids();
    fetchTrades();
}

// 获取系统状态
async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // 更新状态指示器
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        const uptimeElem = document.querySelector('.uptime');
        
        statusDot.className = 'status-dot ' + data.status;
        statusText.textContent = data.status === 'running' ? '运行中' : '已停止';
        
        // 格式化运行时间
        const uptime = formatUptime(data.uptime);
        uptimeElem.textContent = `运行时间: ${uptime}`;
        
        // 更新网格数量
        document.getElementById('grid-count').textContent = data.grid_count;
    } catch (error) {
        console.error('获取系统状态失败:', error);
    }
}

// 获取统计数据
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        // 更新统计数据
        document.getElementById('total-profit').textContent = formatNumber(data.total_profit, 2) + ' USDT';
        document.getElementById('total-trades').textContent = data.total_trades;
        document.getElementById('active-orders').textContent = data.active_orders;
    } catch (error) {
        console.error('获取统计数据失败:', error);
    }
}

// 获取网格列表
async function fetchGrids() {
    try {
        const response = await fetch('/api/grids');
        const data = await response.json();
        const gridList = document.getElementById('grid-list');
        
        if (data.grids.length === 0) {
            gridList.innerHTML = '<div class="no-data">暂无网格策略</div>';
            return;
        }
        
        let html = '';
        data.grids.forEach(grid => {
            html += createGridCard(grid);
        });
        
        gridList.innerHTML = html;
        
        // 添加网格卡片点击事件
        document.querySelectorAll('.grid-card').forEach(card => {
            card.addEventListener('click', () => {
                const gridId = card.dataset.gridId;
                selectGrid(gridId);
            });
        });
        
        // 更新进度条
        updateProgressBars();
    } catch (error) {
        console.error('获取网格列表失败:', error);
    }
}

// 获取交易记录
async function fetchTrades(gridId = null) {
    try {
        let url = '/api/trades?limit=10';
        if (gridId) {
            url += `&grid_id=${gridId}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        const tradesBody = document.getElementById('trades-body');
        
        if (data.trades.length === 0) {
            tradesBody.innerHTML = '<tr><td colspan="7" class="no-data">暂无交易记录</td></tr>';
            return;
        }
        
        let html = '';
        data.trades.forEach(trade => {
            html += createTradeRow(trade);
        });
        
        tradesBody.innerHTML = html;
    } catch (error) {
        console.error('获取交易记录失败:', error);
    }
}

// 创建网格卡片HTML
function createGridCard(grid) {
    const statusClass = grid.status === 'active' ? 'active' : 
                      grid.status === 'error' ? 'error' : 'inactive';
    
    return `
        <div class="grid-card" data-grid-id="${grid.id}">
            <div class="grid-card-header">
                <div class="grid-title">${grid.symbol} - ${grid.exchange}</div>
                <div class="grid-status ${statusClass}">
                    ${grid.status === 'active' ? '运行中' : 
                      grid.status === 'error' ? '错误' : '已停止'}
                </div>
            </div>
            <div class="grid-info">
                <div class="grid-info-item">
                    <span class="grid-info-label">网格范围:</span>
                    <span class="grid-info-value">${grid.low_price} - ${grid.high_price}</span>
                </div>
                <div class="grid-info-item">
                    <span class="grid-info-label">当前价格:</span>
                    <span class="grid-info-value">${grid.current_price}</span>
                </div>
                <div class="grid-info-item">
                    <span class="grid-info-label">网格数量:</span>
                    <span class="grid-info-value">${grid.grid_count}</span>
                </div>
                <div class="grid-info-item">
                    <span class="grid-info-label">投资额:</span>
                    <span class="grid-info-value">${grid.investment} ${grid.quote_asset}</span>
                </div>
                <div class="grid-info-item">
                    <span class="grid-info-label">收益:</span>
                    <span class="grid-info-value ${grid.profit >= 0 ? 'positive' : 'negative'}">
                        ${formatNumber(grid.profit, 4)} ${grid.quote_asset}
                    </span>
                </div>
                <div class="grid-info-item">
                    <span class="grid-info-label">收益率:</span>
                    <span class="grid-info-value ${grid.profit_rate >= 0 ? 'positive' : 'negative'}">
                        ${formatNumber(grid.profit_rate * 100, 2)}%
                    </span>
                </div>
            </div>
            <div class="grid-progress">
                <div class="progress-bar">
                    <div class="progress-fill" data-min="${grid.low_price}" 
                         data-max="${grid.high_price}" 
                         data-current="${grid.current_price}"></div>
                </div>
            </div>
        </div>
    `;
}

// 创建交易记录行HTML
function createTradeRow(trade) {
    const directionClass = trade.side === 'buy' ? 'buy' : 'sell';
    const profitClass = trade.profit >= 0 ? 'positive' : 'negative';
    
    return `
        <tr>
            <td>${formatTimestamp(trade.timestamp)}</td>
            <td>${trade.grid_id.substring(0, 6)}...</td>
            <td>${trade.symbol}</td>
            <td><span class="trade-direction ${directionClass}">
                ${trade.side === 'buy' ? '买入' : '卖出'}
            </span></td>
            <td>${trade.price}</td>
            <td>${trade.amount}</td>
            <td class="trade-profit ${profitClass}">
                ${trade.profit ? formatNumber(trade.profit, 4) : '-'}
            </td>
        </tr>
    `;
}

// 更新所有进度条
function updateProgressBars() {
    document.querySelectorAll('.progress-fill').forEach(bar => {
        const min = parseFloat(bar.dataset.min);
        const max = parseFloat(bar.dataset.max);
        const current = parseFloat(bar.dataset.current);
        
        // 计算百分比位置
        const percentage = ((current - min) / (max - min)) * 100;
        bar.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
    });
}

// 选择网格
function selectGrid(gridId) {
    selectedGridId = gridId;
    
    // 高亮选中的网格卡片
    document.querySelectorAll('.grid-card').forEach(card => {
        if (card.dataset.gridId === gridId) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });
    
    // 重新获取该网格的交易记录
    fetchTrades(gridId);
}

// 格式化数字
function formatNumber(num, decimals = 0) {
    if (num === undefined || num === null) return '-';
    return Number(num).toFixed(decimals);
}

// 格式化时间戳
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 格式化运行时间
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    let result = '';
    if (days > 0) result += `${days}天 `;
    if (hours > 0 || days > 0) result += `${hours}小时 `;
    result += `${minutes}分钟`;
    
    return result;
}