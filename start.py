#!/usr/bin/env python3
"""
启动脚本
"""

import os
import sys
import uvicorn
from app.utils.logger import logger

def check_environment():
    """检查环境配置"""
    # 检查.env文件
    if not os.path.exists('.env'):
        print("❌ 错误: 找不到.env文件")
        print("💡 请复制 .env.example 为 .env 并配置你的API信息")
        return False
    
    # 检查API密钥配置
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'AI_API_KEY=' in content:
                for line in content.split('\n'):
                    if line.startswith('AI_API_KEY=') and len(line.split('=', 1)[1].strip()) > 0:
                        return True
                print("⚠️  警告: AI_API_KEY 未配置")
                print("💡 请编辑 .env 文件，配置你的API密钥")
                return False
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False
    
    return True

def initialize_database():
    """初始化数据库"""
    print("🔧 初始化数据库...")
    from app.db.database import engine
    from app.db.models import Base
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建成功")
        logger.log_database_operation("CREATE_TABLES", "ALL", data={"status": "success"})
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        logger.log_error(e, "数据库初始化失败")
        return False

if __name__ == "__main__":
    print("🚀 启动本地AI助手...")
    
    # 环境检查
    if not check_environment():
        sys.exit(1)
    
    # 记录服务启动
    logger.log_startup()
    
    # 数据库初始化
    if not initialize_database():
        sys.exit(1)
    
    print("\n🎉 启动成功！")
    print("📱 前端界面: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("⏹️  按 Ctrl+C 停止服务")
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)