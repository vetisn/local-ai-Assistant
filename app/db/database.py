# app/db/database.py
import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# SQLite 需要 check_same_thread=False
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def migrate_database():
    """数据库迁移 - 添加新列（自动执行）"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        return  # 数据库不存在，跳过迁移
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查并添加 models_config 列到 providers 表
        cursor.execute("PRAGMA table_info(providers)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'models_config' not in columns:
            cursor.execute("ALTER TABLE providers ADD COLUMN models_config TEXT")
            conn.commit()
        
        # 检查并添加 tool_calls、thinking_content 和 vision_content 列到 messages 表
        cursor.execute("PRAGMA table_info(messages)")
        msg_columns = [col[1] for col in cursor.fetchall()]
        
        if 'tool_calls' not in msg_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN tool_calls TEXT")
            conn.commit()
        
        if 'thinking_content' not in msg_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN thinking_content TEXT")
            conn.commit()
        
        if 'vision_content' not in msg_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN vision_content TEXT")
            conn.commit()
        
        if 'message_events' not in msg_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN message_events TEXT")
            conn.commit()
        
        # 检查并添加 processed 列到 uploaded_files 表
        cursor.execute("PRAGMA table_info(uploaded_files)")
        file_columns = [col[1] for col in cursor.fetchall()]
        
        if 'processed' not in file_columns:
            cursor.execute("ALTER TABLE uploaded_files ADD COLUMN processed INTEGER DEFAULT 0")
            conn.commit()
        
        conn.close()
    except Exception:
        pass  # 静默处理迁移错误


# 模块加载时自动执行迁移
migrate_database()
