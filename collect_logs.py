#!/usr/bin/env python3
"""
日志收集脚本
用于收集问题诊断所需的日志信息
"""

import os
import sys
import zipfile
import json
from datetime import datetime, timedelta
from pathlib import Path

def get_system_info():
    """获取系统信息"""
    import platform
    
    info = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "working_directory": os.getcwd(),
    }
    
    # 检查关键文件是否存在
    key_files = [".env", "requirements.txt", "start.py", "app.db"]
    info["files_status"] = {}
    for file in key_files:
        info["files_status"][file] = os.path.exists(file)
    
    # 检查关键目录
    key_dirs = ["app", "frontend", "logs", "uploaded_files"]
    info["dirs_status"] = {}
    for dir_name in key_dirs:
        info["dirs_status"][dir_name] = os.path.isdir(dir_name)
    
    return info

def collect_recent_logs(hours=24):
    """收集最近N小时的日志"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("❌ logs目录不存在")
        return {}
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    collected_logs = {}
    
    log_files = ["main.log", "api.log", "chat.log", "token.log", "database.log", "error.log"]
    
    for log_file in log_files:
        log_path = logs_dir / log_file
        if not log_path.exists():
            continue
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 过滤最近的日志
            recent_lines = []
            for line in lines:
                try:
                    # 尝试解析时间戳
                    if len(line) > 19:
                        timestamp_str = line[:19]
                        log_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        if log_time >= cutoff_time:
                            recent_lines.append(line)
                except:
                    # 如果无法解析时间戳，保留该行
                    recent_lines.append(line)
            
            if recent_lines:
                collected_logs[log_file] = recent_lines
                print(f"✅ 收集 {log_file}: {len(recent_lines)} 行")
            else:
                print(f"ℹ️  {log_file}: 无最近日志")
                
        except Exception as e:
            print(f"❌ 读取 {log_file} 失败: {e}")
    
    return collected_logs

def create_log_package(output_file="logs_package.zip", hours=24):
    """创建日志包"""
    print(f"🔍 收集最近 {hours} 小时的日志...")
    
    # 收集系统信息
    system_info = get_system_info()
    print("✅ 系统信息收集完成")
    
    # 收集日志
    logs = collect_recent_logs(hours)
    
    if not logs and not system_info:
        print("❌ 没有找到任何日志或系统信息")
        return False
    
    # 创建ZIP包
    try:
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加系统信息
            system_info_json = json.dumps(system_info, indent=2, ensure_ascii=False)
            zipf.writestr("system_info.json", system_info_json)
            
            # 添加日志文件
            for log_file, lines in logs.items():
                log_content = ''.join(lines)
                zipf.writestr(f"logs/{log_file}", log_content)
            
            # 添加README
            readme_content = f"""# 日志包说明

生成时间: {datetime.now().isoformat()}
收集范围: 最近 {hours} 小时
包含文件: {len(logs)} 个日志文件

## 文件说明
- system_info.json: 系统环境信息
- logs/: 各类日志文件

## 使用方法
1. 将此ZIP文件发送给技术支持
2. 或在GitHub Issue中上传此文件
3. 请确保已移除敏感信息

## 隐私说明
- API密钥已自动脱敏
- 但可能包含对话内容，请谨慎分享
"""
            zipf.writestr("README.txt", readme_content)
        
        print(f"✅ 日志包创建成功: {output_file}")
        print(f"📦 包含 {len(logs)} 个日志文件")
        
        # 显示文件大小
        file_size = os.path.getsize(output_file)
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        
        print(f"📏 文件大小: {size_str}")
        return True
        
    except Exception as e:
        print(f"❌ 创建日志包失败: {e}")
        return False

def main():
    """主函数"""
    print("📋 本地AI助手 - 日志收集工具")
    print("=" * 50)
    
    # 检查是否在正确的目录
    if not os.path.exists("start.py"):
        print("❌ 错误: 请在项目根目录运行此脚本")
        sys.exit(1)
    
    # 获取用户输入
    try:
        hours = input("收集最近多少小时的日志？(默认24小时): ").strip()
        hours = int(hours) if hours else 24
        
        if hours <= 0:
            print("❌ 小时数必须大于0")
            sys.exit(1)
            
    except ValueError:
        print("❌ 请输入有效的数字")
        sys.exit(1)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"logs_package_{timestamp}.zip"
    
    # 创建日志包
    success = create_log_package(output_file, hours)
    
    if success:
        print("\n🎉 日志收集完成！")
        print(f"📁 文件位置: {os.path.abspath(output_file)}")
        print("\n📤 反馈问题时请提供:")
        print("1. 详细的问题描述")
        print("2. 重现步骤")
        print("3. 此日志包文件")
        print("\n🔗 问题反馈地址:")
        print("- GitHub Issues: https://github.com/your-repo/issues")
        print("- 邮件: your-email@example.com")
        
        # 隐私提醒
        print("\n⚠️  隐私提醒:")
        print("- 日志包可能包含对话内容")
        print("- API密钥已自动脱敏")
        print("- 请确认无敏感信息后再分享")
        
    else:
        print("\n❌ 日志收集失败")
        sys.exit(1)

if __name__ == "__main__":
    main()