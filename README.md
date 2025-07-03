# Girdbot_hedge 网格量化交易系统

Girdbot_hedge 是一个轻量级的加密货币网格量化交易系统，专为在单一VPS上高效运行而设计。系统支持在不同账户或交易所之间执行相同网格策略，实现自动化交易和对冲操作。

## 功能特点

- **网格交易策略**：在预设价格范围内自动下单买入和卖出，捕捉市场波动带来的利润
- **多账户支持**：支持在同一交易所的多个账户上执行同一策略
- **跨交易所对冲**：支持在不同交易所之间执行对冲交易
- **高效轻量**：无需数据库，使用文件存储，适合在单一VPS上运行
- **实时监控**：提供Web界面查看策略执行情况和交易记录
- **安全可靠**：支持API密钥加密存储，错误恢复机制
- **可扩展设计**：模块化架构，便于添加新交易所和策略

## 系统架构

系统由以下核心组件构成：

1. **核心引擎**：负责系统基础运行，处理事件和任务调度
2. **策略模块**：实现网格交易核心逻辑
3. **交易接口**：与交易所API通信
4. **配置管理**：处理系统和策略参数配置
5. **数据记录**：记录交易数据和性能指标
6. **Web监控**：提供基本状态监控和日志查看

## 安装部署

### 系统要求

- Python 3.7+
- Linux/Unix操作系统 (推荐Ubuntu 18.04+)
- 2GB+ 内存
- 10GB+ 存储空间

### 安装步骤

1. 克隆代码仓库：

```bash
git clone https://github.com/yourusername/girdbot_hedge.git
cd girdbot_hedge
```

2. 运行安装脚本：

```bash
bash scripts/install.sh
```

安装脚本会自动完成以下操作：
- 创建Python虚拟环境
- 安装所需依赖
- 创建配置文件
- 设置数据目录
- 可选安装Supervisor进程守护

3. 配置系统：

编辑 `config.yaml` 文件，填入您的交易所API密钥和策略参数：

```bash
nano config.yaml
```

4. 启动系统：

使用Python直接启动：
```bash
source venv/bin/activate
python main.py
```

或使用Supervisor启动（推荐用于生产环境）：
```bash
sudo supervisorctl start girdbot
```

## 配置说明

`config.yaml` 文件包含以下主要配置部分：

### 系统配置

```yaml
system:
  log_level: "INFO"  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
  data_dir: "./data"  # 数据存储目录
  enable_web_monitor: true  # 是否启用Web监控
  web_host: "0.0.0.0"  # Web监控服务主机
  web_port: 8080  # Web监控服务端口
  update_interval: 2  # 更新间隔（秒）
```

### 交易所配置

```yaml
exchanges:
  # 主账户配置
  - name: "binance"  # 交易所名称：binance, binance_future
    api_key: "YOUR_API_KEY"  # API密钥
    api_secret: "YOUR_API_SECRET"  # API密钥
    is_primary: true  # 是否主账号
    testnet: false  # 是否使用测试网络
  
  # 对冲账户配置（可选）
  - name: "binance"
    account_alias: "account2"  # 账户别名
    api_key: "SECOND_API_KEY"
    api_secret: "SECOND_API_SECRET"
    testnet: false
```

### 网格策略配置

```yaml
strategies:
  - id: "btc_usdt_grid_1"  # 策略ID，必须唯一
    symbol: "BTC/USDT"  # 交易对
    grid_type: "arithmetic"  # 网格类型：arithmetic（等差）或 geometric（等比）
    low_price: 40000  # 网格下限价格
    high_price: 60000  # 网格上限价格
    grid_number: 20  # 网格数量
    investment: 1000  # 投资额(USDT)
    leverage: 1  # 杠杆倍数（现货=1）
    stop_loss: 38000  # 止损价格（可选）
    take_profit: 62000  # 止盈价格（可选）
    exchanges:  # 执行该策略的交易所
      - exchange_id: "binance"  # 对应上面的交易所配置
      - exchange_id: "binance_account2"  # 对冲账户（可选）
        hedge_mode: true  # 开启对冲模式
        hedge_side: "opposite"  # 对冲方向：opposite（反向）或 same（同向）
```

## Web监控

系统提供简易的Web监控界面，默认访问地址为：`http://你的服务器IP:8080`

监控界面包含以下功能：

1. **系统状态**：显示系统运行状态、运行时间等
2. **策略概览**：显示所有网格策略的状态和性能
3. **交易记录**：显示最近的交易记录
4. **收益统计**：显示策略收益和性能指标

## 日常维护

### 健康检查

系统提供健康检查脚本，可以定期监控系统状态：

```bash
python scripts/health_check.py --restart --notify
```

建议将此脚本添加到crontab定时任务：

```bash
# 每5分钟执行一次健康检查
*/5 * * * * /path/to/girdbot_hedge/scripts/health_check.py --restart --notify >> /path/to/girdbot_hedge/data/logs/health_check.log 2>&1
```

### 日志查看

系统日志位于 `data/logs/` 目录下：

```bash
tail -f data/logs/girdbot.log  # 查看实时日志
```

### 停止系统

使用Python启动的情况：
```bash
# 按Ctrl+C停止
```

使用Supervisor启动的情况：
```bash
sudo supervisorctl stop girdbot
```

## 贡献与支持

如有问题或建议，请提交Issue或Pull Request。

## 许可证

[MIT License](LICENSE)