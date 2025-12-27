#!/usr/bin/env python3
"""
详细的日志记录系统
记录所有重要的事件、错误、API调用、token使用等信息
"""

import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from functools import wraps

# 创建logs目录
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# 配置日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 创建不同类型的日志记录器
def setup_logger(name: str, log_file: str, level=logging.INFO, console_output=False):
    """设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名
        level: 日志级别
        console_output: 是否输出到控制台（默认关闭，减少终端噪音）
    """
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 文件处理器
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, log_file), encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    
    # 仅在需要时添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# 创建各种日志记录器（默认不输出到控制台）
main_logger = setup_logger('main', 'main.log')
api_logger = setup_logger('api', 'api.log')
chat_logger = setup_logger('chat', 'chat.log')
token_logger = setup_logger('token', 'token.log')
error_logger = setup_logger('error', 'error.log', logging.ERROR, console_output=True)  # 错误仍输出到控制台
db_logger = setup_logger('database', 'database.log')

class DetailedLogger:
    """详细日志记录类"""
    
    @staticmethod
    def log_startup():
        """记录服务启动"""
        main_logger.info("=" * 50)
        main_logger.info("本地AI助手服务启动")
        main_logger.info(f"启动时间: {datetime.now()}")
        main_logger.info("=" * 50)
    
    @staticmethod
    def log_api_request(method: str, path: str, params: Dict = None, body: Dict = None):
        """记录API请求"""
        api_logger.info(f"API请求: {method} {path}")
        if params:
            api_logger.info(f"参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
        if body:
            # 敏感信息脱敏
            safe_body = DetailedLogger._sanitize_data(body)
            api_logger.info(f"请求体: {json.dumps(safe_body, ensure_ascii=False, indent=2)}")
    
    @staticmethod
    def log_api_response(status_code: int, response_data: Any = None, execution_time: float = None):
        """记录API响应"""
        api_logger.info(f"API响应: {status_code}")
        if execution_time:
            api_logger.info(f"执行时间: {execution_time:.3f}秒")
        if response_data:
            safe_data = DetailedLogger._sanitize_data(response_data)
            api_logger.info(f"响应数据: {json.dumps(safe_data, ensure_ascii=False, indent=2)}")
    
    @staticmethod
    def log_chat_request(conversation_id: int, user_text: str, model: str = None, 
                        tools_enabled: Dict[str, bool] = None):
        """记录聊天请求"""
        chat_logger.info(f"聊天请求 - 对话ID: {conversation_id}")
        chat_logger.info(f"用户输入: {user_text}")
        chat_logger.info(f"使用模型: {model or '默认'}")
        if tools_enabled:
            chat_logger.info(f"启用工具: {tools_enabled}")
    
    @staticmethod
    def log_chat_context(messages: List[Dict], tools: List[Dict] = None):
        """记录聊天上下文"""
        chat_logger.info(f"上下文消息数量: {len(messages)}")
        
        # 记录每条消息的概要
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:100] + "..." if len(content) > 100 else content
            chat_logger.info(f"消息 {i+1} ({role}): {content_preview}")
        
        if tools:
            chat_logger.info(f"可用工具数量: {len(tools)}")
            for tool in tools:
                tool_name = tool.get('function', {}).get('name', 'unknown')
                chat_logger.info(f"工具: {tool_name}")
    
    @staticmethod
    def log_token_usage(model: str, input_tokens: int, output_tokens: int, 
                       total_tokens: int, estimated: bool = False):
        """记录token使用情况"""
        status = "估算" if estimated else "实际"
        token_logger.info(f"Token使用 ({status}) - 模型: {model}")
        token_logger.info(f"输入Token: {input_tokens}")
        token_logger.info(f"输出Token: {output_tokens}")
        token_logger.info(f"总Token: {total_tokens}")
        token_logger.info(f"Token比率: 输入/输出 = {input_tokens}/{output_tokens}")
    
    @staticmethod
    def log_ai_api_call(api_base: str, model: str, messages_count: int, 
                       tools_count: int = 0, stream: bool = False):
        """记录AI API调用"""
        chat_logger.info(f"AI API调用 - 端点: {api_base}")
        chat_logger.info(f"模型: {model}")
        chat_logger.info(f"消息数量: {messages_count}")
        chat_logger.info(f"工具数量: {tools_count}")
        chat_logger.info(f"流式输出: {stream}")
    
    @staticmethod
    def log_tool_call(tool_name: str, arguments: Dict, result: str = None, error: str = None):
        """记录工具调用"""
        chat_logger.info(f"工具调用: {tool_name}")
        safe_args = DetailedLogger._sanitize_data(arguments)
        chat_logger.info(f"参数: {json.dumps(safe_args, ensure_ascii=False, indent=2)}")
        
        if result:
            result_preview = result[:200] + "..." if len(result) > 200 else result
            chat_logger.info(f"工具结果: {result_preview}")
        
        if error:
            error_logger.error(f"工具调用失败 - {tool_name}: {error}")
    
    @staticmethod
    def log_database_operation(operation: str, table: str, record_id: Any = None, 
                              data: Dict = None, error: str = None):
        """记录数据库操作"""
        db_logger.info(f"数据库操作: {operation} - 表: {table}")
        if record_id:
            db_logger.info(f"记录ID: {record_id}")
        if data:
            safe_data = DetailedLogger._sanitize_data(data)
            db_logger.info(f"数据: {json.dumps(safe_data, ensure_ascii=False, indent=2)}")
        if error:
            error_logger.error(f"数据库操作失败 - {operation} {table}: {error}")
    
    @staticmethod
    def log_error(error: Exception, context: str = None, additional_info: Dict = None):
        """记录错误"""
        error_logger.error(f"错误发生: {type(error).__name__}: {str(error)}")
        if context:
            error_logger.error(f"错误上下文: {context}")
        if additional_info:
            safe_info = DetailedLogger._sanitize_data(additional_info)
            error_logger.error(f"附加信息: {json.dumps(safe_info, ensure_ascii=False, indent=2)}")
        
        # 记录堆栈跟踪
        import traceback
        error_logger.error(f"堆栈跟踪:\n{traceback.format_exc()}")
    
    @staticmethod
    def log_performance(operation: str, duration: float, details: Dict = None):
        """记录性能信息"""
        main_logger.info(f"性能统计 - {operation}: {duration:.3f}秒")
        if details:
            safe_details = DetailedLogger._sanitize_data(details)
            main_logger.info(f"详细信息: {json.dumps(safe_details, ensure_ascii=False, indent=2)}")
    
    @staticmethod
    def _sanitize_data(data: Any) -> Any:
        """脱敏敏感数据"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in ['key', 'token', 'password', 'secret']):
                    sanitized[key] = "***HIDDEN***" if value else None
                else:
                    sanitized[key] = DetailedLogger._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [DetailedLogger._sanitize_data(item) for item in data]
        elif hasattr(data, '__dict__'):
            # 处理对象类型（如SQLAlchemy Session等）
            return f"<{type(data).__name__} object>"
        elif not isinstance(data, (str, int, float, bool, type(None))):
            # 处理其他不可序列化的类型
            return str(data)
        else:
            return data

def log_api_call(func):
    """API调用装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        
        try:
            # 记录请求（过滤掉不可序列化的参数）
            safe_kwargs = {}
            for key, value in kwargs.items():
                if key != 'db':  # 跳过数据库Session对象
                    safe_kwargs[key] = value
            
            DetailedLogger.log_api_request(
                method="POST",  # 大多数是POST
                path=func.__name__,
                params=safe_kwargs
            )
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 记录响应
            execution_time = (datetime.now() - start_time).total_seconds()
            DetailedLogger.log_api_response(
                status_code=200,
                response_data=result,
                execution_time=execution_time
            )
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 安全地记录错误信息
            safe_kwargs = {}
            for key, value in kwargs.items():
                if key != 'db':  # 跳过数据库Session对象
                    safe_kwargs[key] = value
            
            DetailedLogger.log_error(e, f"API调用失败: {func.__name__}", {
                "execution_time": execution_time,
                "function_name": func.__name__,
                "kwargs": safe_kwargs
            })
            raise
    
    return wrapper

# 导出主要的日志记录器
logger = DetailedLogger()