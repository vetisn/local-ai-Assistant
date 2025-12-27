#!/usr/bin/env python3
"""
启动脚本 - 一键启动本地AI助手
首次运行前请先安装依赖: pip install -r requirements.txt
"""

import os
import sys


def initialize_database():
    """初始化数据库（仅在需要时）"""
    db_path = "app.db"
    
    if os.path.exists(db_path):
        return True  # 数据库已存在，迁移在 database.py 中自动处理
    
    print("🔧 首次运行，初始化数据库...")
    from app.db.database import engine
    from app.db.models import Base
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库创建成功")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


if __name__ == "__main__":
    print("🚀 启动本地AI助手...")
    
    if not initialize_database():
        sys.exit(1)
    
    print("\n🎉 启动成功！")
    print("📱 前端界面: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("⏹️  按 Ctrl+C 停止服务")
    
    import uvicorn
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
