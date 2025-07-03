#!/usr/bin/env python3
"""
Girdbot_hedge 健康检查脚本
用于监控Girdbot系统是否正常运行，可通过crontab定期执行

使用方法:
1. 直接运行: python health_check.py
2. 设置crontab定时任务: */5 * * * * /path/to/health_check.py >> /path/to/health_check.log 2>&1
"""

import os
import sys
import json
import time
import socket
import smtplib
import argparse
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from girdbot.utils.config_loader import load_config
    from girdbot.utils.logger import setup_logger
except ImportError:
    print("无法导入Girdbot模块，请确保当前目录正确")
    sys.exit(1)

# 设置日志
logger = setup_logger("health_check")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Girdbot健康检查脚本')
    parser.add_argument('--config', type=str, default=os.path.join(project_root, 'config.yaml'),
                        help='配置文件路径')
    parser.add_argument('--restart', action='store_true',
                        help='如果服务不可用，尝试重启')
    parser.add_argument('--notify', action='store_true',
                        help='启用邮件通知')
    return parser.parse_args()

def check_process_running(process_name="python main.py"):
    """检查进程是否运行"""
    try:
        import subprocess
        output = subprocess.check_output(["ps", "aux"], text=True)
        return process_name in output
    except Exception as e:
        logger.error(f"检查进程运行状态时出错: {e}")
        return False

def check_web_server(host="127.0.0.1", port=8080):
    """检查Web服务器是否可访问"""
    try:
        response = requests.get(f"http://{host}:{port}/api/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            return True, status
        return False, {"error": f"HTTP状态码: {response.status_code}"}
    except requests.RequestException as e:
        return False, {"error": str(e)}

def check_disk_space(path=project_root, min_free_gb=1.0):
    """检查磁盘空间是否充足"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)
        return free_gb >= min_free_gb, {
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free_gb, 2),
            "min_required_gb": min_free_gb
        }
    except Exception as e:
        return False, {"error": str(e)}

def check_memory_usage(max_percent=90.0):
    """检查内存使用率是否过高"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return memory.percent < max_percent, {
            "total_mb": round(memory.total / (1024 ** 2), 2),
            "available_mb": round(memory.available / (1024 ** 2), 2),
            "used_percent": memory.percent,
            "max_percent": max_percent
        }
    except ImportError:
        return True, {"error": "psutil模块未安装，跳过内存检查"}
    except Exception as e:
        return False, {"error": str(e)}

def restart_service():
    """尝试重启服务"""
    try:
        # 首先尝试使用Supervisor重启
        import subprocess
        result = subprocess.run(["supervisorctl", "restart", "girdbot"], 
                               capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(f"无法通过Supervisor重启: {result.stderr}")
            logger.info("尝试通过直接杀死进程并重启的方式...")
            
            # 查找进程PID
            ps_result = subprocess.run(["pgrep", "-f", "python main.py"],
                                     capture_output=True, text=True)
            if ps_result.stdout:
                pid = ps_result.stdout.strip()
                # 杀死进程
                subprocess.run(["kill", pid])
                time.sleep(2)
            
            # 启动新进程
            subprocess.Popen(
                f"cd {project_root} && source venv/bin/activate && python main.py &",
                shell=True
            )
            return True, "服务已通过直接启动方式重新启动"
        return True, "服务已通过Supervisor重新启动"
    except Exception as e:
        return False, f"重启服务失败: {str(e)}"

def send_email_notification(config, subject, message):
    """发送邮件通知"""
    email_config = config.get('notifications', {}).get('email', {})
    if not email_config:
        logger.warning("未配置邮件通知设置")
        return False
    
    try:
        sender = email_config.get('sender')
        recipients = email_config.get('recipients', [])
        smtp_server = email_config.get('smtp_server')
        smtp_port = email_config.get('smtp_port', 587)
        username = email_config.get('username')
        password = email_config.get('password')
        
        if not all([sender, recipients, smtp_server, username, password]):
            logger.warning("邮件配置不完整")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        # 添加服务器信息
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        full_message = f"服务器: {hostname} ({ip_address})\n\n{message}"
        
        msg.attach(MIMEText(full_message, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"已发送邮件通知至 {recipients}")
        return True
    except Exception as e:
        logger.error(f"发送邮件通知失败: {e}")
        return False

def main():
    """主函数"""
    args = parse_arguments()
    
    # 加载配置
    config = load_config(args.config)
    if not config:
        logger.critical("无法加载配置文件")
        return 1
    
    # 检查项目状态
    check_results = {}
    all_checks_passed = True
    
    # 检查进程
    process_running, process_details = True, {}
    if not check_process_running():
        process_running = False
        all_checks_passed = False
        process_details = {"error": "Girdbot进程未运行"}
    check_results["process"] = {
        "status": "OK" if process_running else "FAILED",
        "details": process_details
    }
    
    # 检查Web服务器
    web_enabled = config.get('system', {}).get('enable_web_monitor', False)
    if web_enabled:
        web_host = config.get('system', {}).get('web_host', '127.0.0.1')
        web_port = config.get('system', {}).get('web_port', 8080)
        web_ok, web_details = check_web_server(web_host, web_port)
        if not web_ok:
            all_checks_passed = False
        check_results["web_server"] = {
            "status": "OK" if web_ok else "FAILED",
            "details": web_details
        }
    
    # 检查磁盘空间
    disk_ok, disk_details = check_disk_space()
    if not disk_ok:
        all_checks_passed = False
    check_results["disk_space"] = {
        "status": "OK" if disk_ok else "FAILED",
        "details": disk_details
    }
    
    # 检查内存使用
    memory_ok, memory_details = check_memory_usage()
    if not memory_ok:
        all_checks_passed = False
    check_results["memory"] = {
        "status": "OK" if memory_ok else "FAILED",
        "details": memory_details
    }
    
    # 记录检查结果
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_message = f"健康检查结果 ({current_time}):\n"
    result_message += json.dumps(check_results, indent=2, ensure_ascii=False)
    
    if all_checks_passed:
        logger.info("所有健康检查通过")
        logger.debug(result_message)
    else:
        logger.warning("健康检查失败项目:")
        for check, result in check_results.items():
            if result["status"] == "FAILED":
                logger.warning(f"- {check}: {result['details']}")
        
        # 尝试重启服务
        if args.restart and not process_running:
            restart_ok, restart_msg = restart_service()
            logger.info(f"重启服务: {'成功' if restart_ok else '失败'} - {restart_msg}")
            result_message += f"\n\n重启尝试: {restart_msg}"
        
        # 发送通知
        if args.notify:
            send_email_notification(
                config,
                f"Girdbot健康检查警报 - {socket.gethostname()}",
                result_message
            )
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    sys.exit(main())