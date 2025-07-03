#!/bin/bash
# Girdbot_hedge 安装脚本
# 用于在Linux/Unix系统上安装项目依赖并准备运行环境

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

echo -e "${GREEN}开始安装 Girdbot_hedge...${NC}"
echo "项目路径: $PROJECT_ROOT"

# 检查Python版本
echo -e "${YELLOW}检查Python版本...${NC}"
python3 --version
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 找不到Python3，请先安装Python 3.7+${NC}"
    exit 1
fi

# 创建虚拟环境
echo -e "${YELLOW}创建Python虚拟环境...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}虚拟环境已创建${NC}"
else
    echo -e "${YELLOW}虚拟环境已存在，跳过创建${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装项目依赖...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 创建配置文件
echo -e "${YELLOW}创建配置文件...${NC}"
if [ ! -f "config.yaml" ]; then
    cp config.example.yaml config.yaml
    echo -e "${GREEN}配置文件已创建: config.yaml${NC}"
    echo -e "${YELLOW}请编辑配置文件并添加您的API密钥${NC}"
else
    echo -e "${YELLOW}配置文件已存在，跳过创建${NC}"
fi

# 创建数据目录
echo -e "${YELLOW}创建数据目录...${NC}"
mkdir -p data/logs
chmod -R 755 data

# 安装Supervisor（可选）
echo -e "${YELLOW}是否安装Supervisor用于进程守护? [y/N]${NC}"
read install_supervisor
if [[ $install_supervisor == "y" || $install_supervisor == "Y" ]]; then
    echo -e "${YELLOW}安装Supervisor...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y supervisor
    elif command -v yum &> /dev/null; then
        sudo yum install -y supervisor
    else
        echo -e "${RED}无法自动安装Supervisor，请手动安装${NC}"
    fi
    
    # 配置Supervisor
    echo -e "${YELLOW}配置Supervisor...${NC}"
    sudo cp "$PROJECT_ROOT/scripts/girdbot.conf" /etc/supervisor/conf.d/
    sudo sed -i "s|PROJECT_ROOT|$PROJECT_ROOT|g" /etc/supervisor/conf.d/girdbot.conf
    
    # 重新加载Supervisor配置
    sudo supervisorctl reread
    sudo supervisorctl update
    
    echo -e "${GREEN}Supervisor配置完成${NC}"
    echo -e "${YELLOW}您可以使用以下命令控制服务:${NC}"
    echo "sudo supervisorctl start girdbot"
    echo "sudo supervisorctl stop girdbot"
    echo "sudo supervisorctl status girdbot"
fi

echo -e "${GREEN}安装完成!${NC}"
echo -e "${YELLOW}您可以通过以下命令启动服务:${NC}"
echo "cd $PROJECT_ROOT && source venv/bin/activate && python main.py"
echo -e "${YELLOW}或者使用Supervisor启动(如果已安装):${NC}"
echo "sudo supervisorctl start girdbot"