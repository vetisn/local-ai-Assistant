# app/main.py
from __future__ import annotations

import os
import json
import shutil
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.core.config import settings
from app.db.database import SessionLocal, engine, Base
from app.db import crud, models
from app.ai.ai_manager import AIManager
from app.ai import tools as ai_tools
from app.utils.logger import logger, log_api_call, chat_logger
from app.utils.context_manager import ContextManager

load_dotenv()

# 数据库初始化（可选）
# 通过环境变量控制是否自动初始化数据库
AUTO_INIT_DB = os.getenv("AUTO_INIT_DB", "0") == "1"
if AUTO_INIT_DB:
    Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 如需限制，可改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_bool(value: Optional[Any]) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


ai_manager = AIManager()



# ========== 基础接口 ==========


@app.post("/init-database")
def init_database():
    """手动初始化数据库（创建所有表）"""
    try:
        Base.metadata.create_all(bind=engine)
        return {"success": True, "message": "数据库初始化成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库初始化失败: {str(e)}")


@app.get("/models")
def get_models():
    return {
        "default": settings.AI_MODEL,
        "models": settings.ai_models,
    }


@app.get("/provider/config")
def get_provider_config():
    """
    原有接口：返回当前运行时的 provider 配置。
    现在的实现：仅返回 .env 的静态配置是否存在，真正的多 Provider 管理用 /providers 系列接口。
    """
    has_key = bool(settings.AI_API_KEY.strip())
    return {
        "api_base": settings.AI_API_BASE,
        "has_key": has_key,
        "default_model": settings.AI_MODEL,
        "models": settings.ai_models,
    }


@app.post("/provider/config")
def set_provider_config(
    api_base: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
):
    """
    原有接口：运行时覆盖当前 provider。
    为了兼容旧前端，这里仍然支持 set_provider，但实际上更推荐使用 /providers 管理。
    """
    try:
        ai_manager.set_provider(
            api_base=api_base or settings.AI_API_BASE,
            api_key=api_key or settings.AI_API_KEY,
            default_model=model or settings.AI_MODEL,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True}


# ========== 会话管理 ==========


@app.post("/conversations")
def create_conversation(
    title: Optional[str] = Form("新对话"),
    model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    创建新对话：
    - 若最新对话没有任何消息，则复用该对话，避免无限新增空对话。
    - 否则创建新对话。
    返回字段：
    - conversation: 对话信息
    - reused: 是否复用了现有空对话
    """
    latest = crud.get_latest_conversation(db)
    if latest:
        msg_count = crud.get_conversation_message_count(db, latest.id)
        if msg_count == 0:
            # 复用最新的空对话
            if title and title != latest.title:
                latest = crud.update_conversation_title(db, latest.id, title)
            if model and model != latest.model:
                latest = crud.update_conversation_model(db, latest.id, model)
            return {"conversation": latest.to_dict(), "reused": True}

    conv = crud.create_conversation(db, title=title, model=model)
    return {"conversation": conv.to_dict(), "reused": False}



@app.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    conversations = crud.get_conversations(db)
    return [conv.to_dict() for conv in conversations]


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    crud.delete_conversation(db, conversation_id)
    return {"success": True}


@app.put("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: int,
    title: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    is_pinned: Optional[bool] = Form(None),
    enable_knowledge_base: Optional[bool] = Form(None),
    enable_mcp: Optional[bool] = Form(None),
    enable_web_search: Optional[bool] = Form(None),
    provider_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    conv = crud.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if title is not None:
        conv.title = title
    if model is not None:
        conv.model = model
    if is_pinned is not None:
        conv.is_pinned = parse_bool(is_pinned) or False
    if enable_knowledge_base is not None:
        conv.enable_knowledge_base = parse_bool(enable_knowledge_base) or False
    if enable_mcp is not None:
        conv.enable_mcp = parse_bool(enable_mcp) or False
    if enable_web_search is not None:
        conv.enable_web_search = parse_bool(enable_web_search) or False

    if provider_id is not None:
        conv.provider_id = provider_id

    db.commit()
    db.refresh(conv)
    return conv.to_dict()


@app.post("/conversations/{conversation_id}/title")
def update_conversation_title(
    conversation_id: int,
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    conv = crud.update_conversation_title(db, conversation_id, title)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()



@app.post("/conversations/{conversation_id}/auto-title")
def auto_generate_conversation_title(
    conversation_id: int,
    model: Optional[str] = Form(None),
    first_user_message: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    基于对话内容自动生成标题
    """
    import traceback
    
    conversation = crud.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # 获取对话的前几条消息用于生成标题
    messages_db = crud.get_messages(db, conversation_id)
    # 如果数据库中消息太少，但前端传来了 first_user_message，则把它作为最小上下文
    if len(messages_db) < 2 and not first_user_message:
        raise HTTPException(status_code=400, detail="对话内容不足，无法生成标题")

    # 取前4条消息作为上下文
    context_messages = messages_db[:4]
    if len(context_messages) < 2 and first_user_message:
        # 创建一个临时的用户消息对象样式用于生成标题
        class _TmpMsg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        tmp = _TmpMsg('user', first_user_message)
        # 把临时消息插到最前面
        context_messages = [tmp] + context_messages
    context_text = "\n".join([f"{m.role}: {m.content[:200]}" for m in context_messages])  # 限制每条消息长度
    
    # 构建标题生成的提示
    title_prompt = f"""请为以下对话生成一个简洁的标题（不超过10个字）：

{context_text}

要求：
1. 标题要准确概括对话主题
2. 使用中文
3. 不超过10个字
4. 不要包含引号或特殊符号
5. 直接返回标题，不要其他内容

标题："""

    try:
        # 配置AI Provider
        print(f"配置Provider for conversation {conversation_id}")
        _configure_ai_provider_for_conversation(db, conversation)
        
        # 确定使用的模型：优先参数，其次设置中的 auto_title_model，再次会话/全局默认
        selected_model = model
        if not selected_model:
            setting_model = crud.get_setting(db, "auto_title_model")
            if setting_model and setting_model.value and setting_model.value != "current":
                selected_model = setting_model.value
        if not selected_model:
            selected_model = conversation.model or settings.AI_MODEL

        use_model = selected_model
        print(f"使用模型: {use_model}")
        
        # 调用AI生成标题

        title_messages = [{"role": "user", "content": title_prompt}]
        print(f"调用AI生成标题...")
        
        # 添加超时和重试机制
        try:
            result = ai_manager.chat(title_messages, model=use_model, stream=False)
            # 从结果中提取内容
            if isinstance(result, dict) and "content" in result:
                generated_title = result["content"]
            else:
                generated_title = str(result)
        except Exception as api_error:
            print(f"API调用失败: {api_error}")
            # 如果API调用失败，使用简单的标题生成逻辑
            user_message = context_messages[0].content if context_messages else "新对话"
            generated_title = user_message[:15] + "..." if len(user_message) > 15 else user_message
            print(f"使用备用标题: {generated_title}")
        
        print(f"生成的标题: {generated_title}")
        
        # 清理生成的标题
        generated_title = str(generated_title).strip().replace('"', '').replace("'", "").replace("标题：", "").replace("标题:", "")
        if len(generated_title) > 10:
            generated_title = generated_title[:10]
        
        # 确保标题不为空
        if not generated_title or generated_title.isspace():
            generated_title = "新对话"
        
        # 更新对话标题
        conv = crud.update_conversation_title(db, conversation_id, generated_title)
        return {"title": generated_title, "conversation": conv.to_dict()}
        
    except Exception as e:
        print(f"标题生成错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"标题生成失败: {str(e)}")



@app.post("/conversations/{conversation_id}/pin")
def update_conversation_pin(
    conversation_id: int,
    is_pinned: bool = Form(...),
    db: Session = Depends(get_db),
):
    is_pinned = bool(parse_bool(is_pinned))
    conv = crud.update_conversation_pin(db, conversation_id, is_pinned)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()


@app.post("/conversations/{conversation_id}/model")
def update_conversation_model(
    conversation_id: int,
    model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    conv = crud.update_conversation_model(db, conversation_id, model)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()


# 新增：更新会话功能开关（知识库/MCP/联网搜索）
@app.post("/conversations/{conversation_id}/features")
def update_conversation_features(
    conversation_id: int,
    enable_knowledge_base: Optional[bool] = Form(None),
    enable_mcp: Optional[bool] = Form(None),
    enable_web_search: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
):
    enable_knowledge_base = parse_bool(enable_knowledge_base)
    enable_mcp = parse_bool(enable_mcp)
    enable_web_search = parse_bool(enable_web_search)

    conv = crud.update_conversation_features(
        db,
        conversation_id,
        enable_knowledge_base=enable_knowledge_base,
        enable_mcp=enable_mcp,
        enable_web_search=enable_web_search,
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()


# 新增：绑定 Provider 到会话
@app.post("/conversations/{conversation_id}/provider")
def set_conversation_provider(
    conversation_id: int,
    provider_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    parsed_provider: Optional[int]
    if provider_id in (None, "", "null", "undefined"):
        parsed_provider = None
    else:
        try:
            parsed_provider = int(provider_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid provider_id")

    conv = crud.set_conversation_provider(db, conversation_id, parsed_provider)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()



# ========== 消息与聊天 ==========


@app.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    messages = crud.get_messages(db, conversation_id)
    return [msg.to_dict() for msg in messages]


def _configure_ai_provider_for_conversation(
    db: Session,
    conversation: models.Conversation,
    override_provider_id: Optional[int] = None,
) -> None:
    """
    根据会话绑定的 provider 或覆盖参数，配置 AIManager 当前使用的 provider。
    """
    provider: Optional[models.Provider] = None

    if override_provider_id is not None:
        provider = crud.get_provider(db, override_provider_id)
    elif conversation.provider_id:
        provider = crud.get_provider(db, conversation.provider_id)

    if provider:
        ai_manager.set_provider(
            api_base=provider.api_base,
            api_key=provider.api_key,
            default_model=conversation.model or provider.default_model,
        )
    else:
        # 使用全局默认
        ai_manager.set_provider(
            api_base=settings.AI_API_BASE,
            api_key=settings.AI_API_KEY,
            default_model=conversation.model or settings.AI_MODEL,
        )


def _execute_chat_with_tools(
    messages: List[Dict[str, Any]], 
    tools_list: List[Dict[str, Any]], 
    model: Optional[str],
    conversation_id: int,
    db: Session
) -> tuple[str, Dict[str, Any]]:
    """
    执行带工具的对话，包括工具调用循环
    """
    import json
    from app.ai import tools as ai_tools
    
    # 累计token统计
    total_input_tokens = 0
    total_output_tokens = 0
    
    # 工具调用循环
    current_messages = messages.copy()
    max_iterations = 5  # 防止无限循环
    
    for iteration in range(max_iterations):
        # 调用模型
        data = ai_manager.run_with_tools(current_messages, tools=tools_list, model=model, stream=False)
        
        # 累计token统计
        usage = data.get("usage", {})
        total_input_tokens += usage.get("prompt_tokens", 0)
        total_output_tokens += usage.get("completion_tokens", 0)
        
        message = data["choices"][0]["message"]
        current_messages.append(message)
        
        # 检查是否有工具调用
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # 没有工具调用，返回最终结果
            final_content = message.get("content", "")
            token_info = {
                "model": model or "default",
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens
            }
            return final_content, token_info
        
        # 执行工具调用
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
            
            # 执行工具
            try:
                result = _execute_tool(function_name, function_args, conversation_id, db)
            except Exception as e:
                result = f"工具执行失败: {str(e)}"
            
            # 添加工具调用结果到消息历史
            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result
            })
    
    # 如果达到最大迭代次数，返回最后的消息
    final_content = current_messages[-1].get("content", "达到最大工具调用次数限制")
    token_info = {
        "model": model or "default",
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens
    }
    return final_content, token_info


def _execute_tool(function_name: str, function_args: Dict[str, Any], conversation_id: int, db: Session) -> str:
    """
    执行具体的工具调用
    """
    from app.ai import tools as ai_tools
    
    try:
        if function_name == "get_local_time":
            return ai_tools.run_get_local_time_tool()
        
        elif function_name == "calculate_expression":
            expression = function_args.get("expression", "")
            return ai_tools.run_calculator_tool(expression)
        
        elif function_name == "search_knowledge":
            query = function_args.get("query", "")
            kb_id = function_args.get("kb_id")
            top_k = function_args.get("top_k", 5)
            
            # 创建embedding函数
            def embedding_fn(texts):
                return ai_manager.create_embedding(texts)
            
            return ai_tools.run_search_knowledge_tool(
                query=query,
                kb_id=kb_id,
                top_k=top_k,
                embedding_fn=embedding_fn
            )
        
        elif function_name == "web_search":
            query = function_args.get("query", "")
            source = function_args.get("source", "duckduckgo")
            return ai_tools.run_web_search_tool(query=query, source=source)
        
        else:
            return f"未知的工具: {function_name}"
            
    except Exception as e:
        return f"工具执行错误: {str(e)}"


def _build_tools_for_conversation(
    conversation: models.Conversation,
    enable_knowledge_base: Optional[bool],
    enable_mcp: Optional[bool],
    enable_web_search: Optional[bool],
) -> List[Dict[str, Any]]:
    """
    根据会话默认开关 + 本次请求参数，决定启用哪些 tools。
    优先使用本次请求参数，如果为 None 则回退到 conversation 的设置。
    """
    kb_flag = (
        enable_knowledge_base
        if enable_knowledge_base is not None
        else conversation.enable_knowledge_base
    )
    mcp_flag = (
        enable_mcp if enable_mcp is not None else conversation.enable_mcp
    )
    web_flag = (
        enable_web_search
        if enable_web_search is not None
        else conversation.enable_web_search
    )

    return ai_tools.get_tools(
        enable_knowledge_base=kb_flag,
        enable_mcp=mcp_flag,
        enable_web_search=web_flag,
    )


@app.post("/conversations/{conversation_id}/chat")
@log_api_call
def chat_with_conversation(
    conversation_id: int,
    user_text: str = Form(...),
    model: Optional[str] = Form(None),

    # 新增：本次请求的功能开关（可覆盖会话默认）
    enable_knowledge_base: Optional[bool] = Form(None),
    enable_mcp: Optional[bool] = Form(None),
    enable_web_search: Optional[bool] = Form(None),
    web_search_source: Optional[str] = Form(None),  # 搜索源

    # 新增：指定本次使用的 provider（可选）
    provider_id: Optional[int] = Form(None),

    # 新增：是否流式输出（默认 False）
    stream: bool = Form(False),

    db: Session = Depends(get_db),
):
    from datetime import datetime
    start_time = datetime.now()

    enable_knowledge_base = parse_bool(enable_knowledge_base)
    enable_mcp = parse_bool(enable_mcp)
    enable_web_search = parse_bool(enable_web_search)
    stream = parse_bool(stream) or False
    
    # 记录聊天请求
    tools_enabled = {
        "knowledge_base": enable_knowledge_base,
        "mcp": enable_mcp,
        "web_search": enable_web_search
    }

    logger.log_chat_request(conversation_id, user_text, model, tools_enabled)
    
    conversation = crud.get_conversation(db, conversation_id)
    if not conversation:
        logger.log_error(Exception("Conversation not found"), f"对话ID {conversation_id} 不存在")
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. 写入用户消息
    try:
        user_msg = crud.create_message(db, conversation_id, "user", user_text)
        logger.log_database_operation("CREATE", "messages", user_msg.id, {
            "role": "user", 
            "content_length": len(user_text)
        })
    except Exception as e:
        logger.log_error(e, "创建用户消息失败")
        raise

    # 2. 配置 Provider
    try:
        _configure_ai_provider_for_conversation(db, conversation, override_provider_id=provider_id)
        logger.log_performance("配置Provider", (datetime.now() - start_time).total_seconds())
    except Exception as e:
        logger.log_error(e, "配置Provider失败")
        raise

    # 3. 准备上下文消息
    messages_db = crud.get_messages(db, conversation_id)
    messages: List[Dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in messages_db
    ]

    # 优化上下文，限制对话轮数为6轮
    messages = ContextManager.optimize_messages(messages, max_turns=6)

    # 如果启用了联网搜索，添加系统提示
    web_flag = (
        enable_web_search
        if enable_web_search is not None
        else conversation.enable_web_search
    )
    if web_flag:
        search_source = web_search_source or "duckduckgo"
        system_prompt = f"如需查询最新信息、实时数据或当前事件，请调用 web_search 工具。默认搜索源为 {search_source}。"
        messages.insert(0, {"role": "system", "content": system_prompt})

    # 4. 智能选择工具，减少不必要的工具定义
    conversation_tools = {
        'knowledge_base': enable_knowledge_base if enable_knowledge_base is not None else conversation.enable_knowledge_base,
        'mcp': enable_mcp if enable_mcp is not None else conversation.enable_mcp,
        'web_search': enable_web_search if enable_web_search is not None else conversation.enable_web_search
    }
    
    smart_tools = ContextManager.should_enable_tools(user_text, conversation_tools)
    
    tools_list = _build_tools_for_conversation(
        conversation,
        enable_knowledge_base=smart_tools['knowledge_base'],
        enable_mcp=smart_tools['mcp'],
        enable_web_search=smart_tools['web_search'],
    )

    # 记录聊天上下文
    logger.log_chat_context(messages, tools_list)

    # 如果没有任何工具，就走普通 chat；否则走 run_with_tools
    use_tools = bool(tools_list)

    # 5. 调用大模型
    if not stream:
        try:
            # 记录AI API调用
            logger.log_ai_api_call(
                api_base=ai_manager._provider.api_base,
                model=model or ai_manager._provider.default_model,
                messages_count=len(messages),
                tools_count=len(tools_list),
                stream=False
            )
            
            if use_tools:
                # 执行带工具的对话，包括工具调用循环
                content, token_info = _execute_chat_with_tools(
                    messages, tools_list, model, conversation_id, db
                )
            else:
                result = ai_manager.chat(messages, model=model, stream=False)
                content = result["content"]
                token_info = {
                    "model": result["model"],
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "total_tokens": result["total_tokens"]
                }

            # 记录token使用情况
            logger.log_token_usage(
                model=token_info["model"],
                input_tokens=token_info["input_tokens"],
                output_tokens=token_info["output_tokens"],
                total_tokens=token_info["total_tokens"],
                estimated=token_info.get("estimated", False)
            )

            assistant_msg = crud.create_message(db, conversation_id, "assistant", content, token_info)
            logger.log_database_operation("CREATE", "messages", assistant_msg.id, {
                "role": "assistant",
                "content_length": len(content),
                "token_info": token_info
            })
            
            # 记录整体性能
            total_time = (datetime.now() - start_time).total_seconds()
            logger.log_performance("聊天完成", total_time, {
                "conversation_id": conversation_id,
                "use_tools": use_tools,
                "message_length": len(user_text),
                "response_length": len(content)
            })
            
            return {
                "user_message": {
                    "id": user_msg.id,
                    "role": user_msg.role,
                    "content": user_msg.content,
                    "created_at": user_msg.created_at.isoformat() if user_msg.created_at else None,
                },
                "user_message_id": user_msg.id,  # 明确返回用户消息ID，用于前端确认消息已保存
                "assistant_message": {
                    "id": assistant_msg.id,
                    "role": assistant_msg.role,
                    "content": assistant_msg.content,
                    "created_at": assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
                    "model": assistant_msg.model,
                    "input_tokens": assistant_msg.input_tokens,
                    "output_tokens": assistant_msg.output_tokens,
                    "total_tokens": assistant_msg.total_tokens,
                },
                "token_info": token_info,
            }
        except Exception as e:
            logger.log_error(e, "AI调用失败", {
                "conversation_id": conversation_id,
                "model": model,
                "use_tools": use_tools,
                "messages_count": len(messages),
                "tools_count": len(tools_list)
            })
            raise HTTPException(status_code=500, detail=f"AI调用失败: {str(e)}")

    # 流式：返回 StreamingResponse，最终拼接完整文本写入 DB
    def event_stream():
        accumulated = []
        token_info = None
        
        # 记录流式输出开始
        chat_logger.info(f"[STREAM] 开始流式输出，对话ID: {conversation_id}, 模型: {model}")
        
        # 首先发送 ack 事件，确认用户消息已保存
        yield f"event: ack\n"
        yield f"data: {{\"user_message_id\": {user_msg.id}}}\n\n"
        
        if use_tools:
            # 流式 + tools：执行工具调用并流式返回
            try:
                chat_logger.info(f"[STREAM] 使用工具模式")
                # 执行带工具的对话，包括工具调用循环
                content, token_info = _execute_chat_with_tools(
                    messages, tools_list, model, conversation_id, db
                )
                
                chat_logger.info(f"[STREAM] 工具调用完成，内容长度: {len(content)}")
                
                # 流式返回：按块发送 JSON，保留换行等格式
                import json as _json
                chunk_size = 512
                chunk_count = 0
                for i in range(0, len(content), chunk_size):
                    chunk = content[i : i + chunk_size]
                    payload = _json.dumps({"text": chunk}, ensure_ascii=False)
                    accumulated.append(chunk)
                    chunk_count += 1
                    yield f"data: {payload}\n\n"
                
                chat_logger.info(f"[STREAM] 发送完成，共 {chunk_count} 个块")
                
                # 发送token信息
                yield f"event: meta\n"
                yield f"data: {json.dumps(token_info)}\n\n"
                yield "data: [DONE]\n\n"
                
                chat_logger.info(f"[STREAM] 发送 [DONE] 标记")
                
                # 写入数据库
                full_text = "".join(accumulated)

                try:
                    logger.log_token_usage(
                        model=token_info.get("model", model or "default"),
                        input_tokens=token_info.get("input_tokens", 0),
                        output_tokens=token_info.get("output_tokens", 0),
                        total_tokens=token_info.get("total_tokens", 0),
                        estimated=token_info.get("estimated", False),
                    )
                except Exception:
                    pass
                crud.create_message(db, conversation_id, "assistant", full_text, token_info)
                
            except Exception as e:
                chat_logger.error(f"[STREAM] 工具模式错误: {str(e)}")
                yield f"data: [错误] {str(e)}\n\n"
                yield "data: [DONE]\n\n"

        else:
            try:
                chat_logger.info(f"[STREAM] 普通流式模式")
                chunk_count = 0
                # 普通流式对话，直接消费 include_usage 终结包
                for chunk in ai_manager.chat(messages, model=model, stream=True):
                    if isinstance(chunk, dict):
                        if chunk.get("type") == "usage":
                            token_info = chunk.get("usage")
                            continue
                        delta = chunk.get("content", "")
                    else:
                        delta = str(chunk)

                    if delta:
                        accumulated.append(delta)
                        chunk_count += 1
                        # 使用 JSON 编码以保留换行符（SSE 中换行符会破坏格式）
                        yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
                
                full_text = "".join(accumulated)
                chat_logger.info(f"[STREAM] 流式输出完成，共 {chunk_count} 个块，总长度: {len(full_text)}")

                # 如果流式没给 usage，则估算
                if not token_info:
                    estimated_input = max(1, len(json.dumps(messages, ensure_ascii=False)) // 4)
                    estimated_output = max(1, len(full_text) // 4)
                    token_info = {
                        "model": model or "default",
                        "input_tokens": estimated_input,
                        "output_tokens": estimated_output,
                        "total_tokens": estimated_input + estimated_output,
                        "estimated": True,
                    }

                # 发送token信息
                yield f"event: meta\n"
                yield f"data: {json.dumps(token_info)}\n\n"
                yield "data: [DONE]\n\n"
                
                chat_logger.info(f"[STREAM] 发送 [DONE] 标记")
                
                # 完成后将完整回复写入数据库
                try:
                    logger.log_token_usage(
                        model=token_info.get("model", model or "default"),
                        input_tokens=token_info.get("input_tokens", 0),
                        output_tokens=token_info.get("output_tokens", 0),
                        total_tokens=token_info.get("total_tokens", 0),
                        estimated=token_info.get("estimated", False),
                    )
                except Exception:
                    pass

                crud.create_message(db, conversation_id, "assistant", full_text, token_info)
                
            except Exception as e:
                chat_logger.error(f"[STREAM] 普通模式错误: {str(e)}")
                yield f"data: [错误] {str(e)}\n\n"
                yield "data: [DONE]\n\n"


    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ========== 文件上传（对话级） ==========


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/upload")
def upload_file(
    conversation_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    conversation = crud.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    save_dir = os.path.join(UPLOAD_DIR, str(conversation_id))
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    record = crud.create_uploaded_file(db, conversation_id, file.filename, save_path)
    return record.to_dict()


@app.get("/conversations/{conversation_id}/files")
def list_conversation_files(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    files = crud.get_uploaded_files(db, conversation_id)
    return [file.to_dict() for file in files]


@app.delete("/files/{file_id}")
def delete_conversation_file(file_id: int, db: Session = Depends(get_db)):
    file_record = crud.get_uploaded_file(db, file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    # 删除本地文件
    try:
        if os.path.exists(file_record.filepath):
            os.remove(file_record.filepath)
    except Exception:
        pass

    crud.delete_uploaded_file(db, file_id)
    return {"success": True}


@app.get("/files/{path:path}")
def get_file(path: str):
    file_path = os.path.join(UPLOAD_DIR, path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ========== Provider 管理接口（新增） ==========


@app.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    providers = crud.list_providers(db)
    return [provider.to_dict() for provider in providers]


@app.post("/providers")
def create_provider(
    name: str = Form(...),
    api_base: str = Form(...),
    api_key: str = Form(...),
    default_model: str = Form(...),
    models_str: Optional[str] = Form(None),
    is_default: bool = Form(False),
    db: Session = Depends(get_db),
):
    try:
        # 检查是否已存在同名Provider
        existing = crud.get_provider_by_name(db, name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Provider名称 '{name}' 已存在")
        
        provider = crud.create_provider(
            db,
            name=name,
            api_base=api_base,
            api_key=api_key,
            default_model=default_model,
            models_str=models_str,
            is_default=is_default,
        )
        return provider.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        print(f"创建Provider失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"创建Provider失败: {str(e)}")


@app.post("/providers/{provider_id}")
def update_provider(
    provider_id: int,
    name: Optional[str] = Form(None),
    api_base: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    default_model: Optional[str] = Form(None),
    models_str: Optional[str] = Form(None),
    is_default: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
):
    provider = crud.update_provider(
        db,
        provider_id,
        name=name,
        api_base=api_base,
        api_key=api_key,
        default_model=default_model,
        models_str=models_str,
        is_default=is_default,
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider.to_dict()


@app.delete("/providers/{provider_id}")
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    crud.delete_provider(db, provider_id)
    return {"success": True}


@app.get("/providers/{provider_id}/models")
def get_provider_models(provider_id: int, db: Session = Depends(get_db)):
    """获取指定Provider的模型列表"""
    provider = crud.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    models = []
    if provider.models:
        models = [m.strip() for m in provider.models.split(",") if m.strip()]
    else:
        models = [provider.default_model]
    
    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "default_model": provider.default_model,
        "models": models,
    }


@app.get("/models/all")
def get_all_models(db: Session = Depends(get_db)):
    """获取所有Provider的模型列表，用于前端统一显示"""
    providers = crud.list_providers(db)
    all_models = set()
    
    # 添加全局默认模型
    all_models.update(settings.ai_models)
    
    # 添加所有Provider的模型
    for provider in providers:
        if provider.models:
            provider_models = [m.strip() for m in provider.models.split(",") if m.strip()]
            all_models.update(provider_models)
        else:
            all_models.add(provider.default_model)
    
    return {
        "default": settings.AI_MODEL,
        "models": sorted(list(all_models)),
        "providers": [
            {
                "id": p.id,
                "name": p.name,
                "default_model": p.default_model,
                "models": [m.strip() for m in p.models.split(",") if p.models and m.strip()] or [p.default_model]
            }
            for p in providers
        ]
    }


# ========== 知识库多库管理 + 向量构建接口（新增） ==========


@app.get("/knowledge/bases")
def list_knowledge_bases(db: Session = Depends(get_db)):
    bases = crud.list_knowledge_bases(db)
    return [base.to_dict() for base in bases]


@app.post("/knowledge/bases")
def create_knowledge_base(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    kb = crud.create_knowledge_base(db, name=name, description=description)
    return kb.to_dict()


@app.delete("/knowledge/bases/{kb_id}")
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    crud.delete_knowledge_base(db, kb_id)
    return {"success": True}


@app.get("/knowledge/documents")
def list_knowledge_documents(
    kb_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    documents = crud.list_knowledge_documents(db, kb_id=kb_id)
    return [doc.to_dict() for doc in documents]


@app.post("/knowledge/upload")
def upload_knowledge_file(
    kb_id: Optional[int] = Form(None),
    embedding_model: Optional[str] = Form(None),
    extract_graph: Optional[bool] = Form(True),  # 新增：是否提取知识图谱
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    上传一个文件到指定知识库：
    1. 保存原始文件；
    2. 抽取文本；
    3. 切分为若干段落；
    4. 调用 embedding 接口生成向量；
    5. 存入 KnowledgeDocument + KnowledgeChunk；
    6. （可选）提取知识图谱实体和关系。
    """
    # 验证向量模型
    selected_embedding_model = embedding_model or settings.EMBEDDING_MODEL
    if selected_embedding_model and selected_embedding_model not in settings.embedding_models:
        # 如果没有配置向量模型，跳过向量化
        selected_embedding_model = None
    
    # 1. 保存文件
    kb_dir = os.path.join(UPLOAD_DIR, "knowledge")
    os.makedirs(kb_dir, exist_ok=True)
    save_path = os.path.join(kb_dir, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. 简单读取文本
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="暂不支持非 UTF-8 文本文件作为知识库源。")

    # 3. 简单切分段落
    paragraphs: List[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        paragraphs.append(line)

    if not paragraphs:
        raise HTTPException(status_code=400, detail="文件中未检测到有效文本内容。")

    # 4. 生成向量（如果有向量模型）
    embeddings = None
    if selected_embedding_model:
        try:
            embeddings = ai_manager.create_embedding(paragraphs, model=selected_embedding_model)
        except Exception as e:
            print(f"向量生成失败: {e}")
            embeddings = None

    # 5. 写入 DB
    doc = crud.create_knowledge_document(
        db,
        kb_id=kb_id,
        file_name=file.filename,
        file_path=save_path,
        content=content[:2000],
        embedding_model=selected_embedding_model,
    )

    # 存储向量块
    if embeddings and len(embeddings) == len(paragraphs):
        chunks_data = []
        for idx, (para, emb) in enumerate(zip(paragraphs, embeddings)):
            chunks_data.append((idx, para, emb))
        crud.create_knowledge_chunks(db, document_id=doc.id, chunks=chunks_data)

    # 6. 提取知识图谱（可选）
    graph_result = None
    if extract_graph:
        try:
            from app.ai.knowledge_graph import extract_from_chunks
            
            # 使用前几个段落提取实体关系
            sample_chunks = paragraphs[:20]  # 限制处理量
            entities, relations = extract_from_chunks(
                sample_chunks, 
                ai_manager,
                batch_size=5
            )
            
            if entities or relations:
                graph_result = crud.batch_create_entities_and_relations(
                    db,
                    kb_id=kb_id,
                    document_id=doc.id,
                    entities=entities,
                    relations=relations,
                )
        except Exception as e:
            print(f"知识图谱提取失败: {e}")
            graph_result = {"error": str(e)}

    return {
        "success": True, 
        "document": doc.to_dict(),
        "chunks_count": len(paragraphs) if embeddings else 0,
        "graph": graph_result,
    }


# ========== 系统设置接口（新增） ==========

@app.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    """获取系统设置"""
    # 从数据库获取保存的设置
    saved_settings = crud.get_all_settings(db)
    settings_dict = {s.key: s.value for s in saved_settings}
    
    return {
        "font_size": settings_dict.get("font_size", "13px"),
        "auto_title_model": settings_dict.get("auto_title_model", "current"),
        "default_search_source": settings_dict.get("default_search_source", "duckduckgo"),
        "tavily_api_key": settings_dict.get("tavily_api_key", ""),
        "global_api_key": settings_dict.get("global_api_key", getattr(settings, 'AI_API_KEY', '')),
        "global_api_base": settings_dict.get("global_api_base", getattr(settings, 'AI_API_BASE', 'https://api.openai.com/v1')),
        "global_default_model": settings_dict.get("global_default_model", getattr(settings, 'AI_MODEL', 'gpt-4o-mini')),
    }


@app.post("/settings")
def update_settings(
    font_size: Optional[str] = Form(None),
    auto_title_model: Optional[str] = Form(None),
    theme: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    default_search_source: Optional[str] = Form(None),
    tavily_api_key: Optional[str] = Form(None),
    global_api_key: Optional[str] = Form(None),
    global_api_base: Optional[str] = Form(None),
    global_default_model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """更新系统设置"""
    settings_data = {}
    
    # 保存设置到数据库
    if font_size:
        crud.set_setting(db, "font_size", font_size)
        settings_data["font_size"] = font_size
    if auto_title_model:
        crud.set_setting(db, "auto_title_model", auto_title_model)
        settings_data["auto_title_model"] = auto_title_model
    if theme:
        crud.set_setting(db, "theme", theme)
        settings_data["theme"] = theme
    if language:
        crud.set_setting(db, "language", language)
        settings_data["language"] = language
    if default_search_source:
        crud.set_setting(db, "default_search_source", default_search_source)
        settings_data["default_search_source"] = default_search_source
    if tavily_api_key is not None:  # 允许空字符串
        crud.set_setting(db, "tavily_api_key", tavily_api_key)
        settings_data["tavily_api_key"] = tavily_api_key
    
    # 新增：全局API配置
    if global_api_key is not None:
        crud.set_setting(db, "global_api_key", global_api_key)
        settings_data["global_api_key"] = global_api_key
        # 同时更新AI管理器的配置
        ai_manager._provider.api_key = global_api_key
        # 更新环境变量（如果需要持久化）
        import os
        os.environ["AI_API_KEY"] = global_api_key
        
    if global_api_base is not None:
        crud.set_setting(db, "global_api_base", global_api_base)
        settings_data["global_api_base"] = global_api_base
        ai_manager._provider.api_base = global_api_base.rstrip("/")
        os.environ["AI_API_BASE"] = global_api_base
        
    if global_default_model is not None:
        crud.set_setting(db, "global_default_model", global_default_model)
        settings_data["global_default_model"] = global_default_model
        ai_manager._provider.default_model = global_default_model
        os.environ["AI_MODEL"] = global_default_model
    
    return {"success": True, "settings": settings_data}


@app.get("/logs/export")
def export_logs(hours: int = 24):
    """导出日志文件"""
    import zipfile
    import io
    from datetime import datetime, timedelta
    from pathlib import Path
    
    logs_dir = Path("logs")
    if not logs_dir.exists():
        raise HTTPException(status_code=404, detail="日志目录不存在")
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # 创建内存中的 ZIP 文件
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加系统信息
        import platform
        system_info = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hours_collected": hours
        }
        zipf.writestr("system_info.json", json.dumps(system_info, indent=2, ensure_ascii=False))
        
        # 收集日志文件
        log_files = ["main.log", "api.log", "chat.log", "token.log", "database.log", "error.log"]
        collected_count = 0
        
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
                        if len(line) > 19:
                            timestamp_str = line[:19]
                            log_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            if log_time >= cutoff_time:
                                recent_lines.append(line)
                    except:
                        recent_lines.append(line)
                
                if recent_lines:
                    zipf.writestr(f"logs/{log_file}", ''.join(recent_lines))
                    collected_count += 1
            except Exception:
                pass
        
        # 添加说明文件
        readme = f"""日志导出
生成时间: {datetime.now().isoformat()}
收集范围: 最近 {hours} 小时
文件数量: {collected_count}
"""
        zipf.writestr("README.txt", readme)
    
    zip_buffer.seek(0)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"debug_logs_{timestamp}.zip"
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/search/test")
def test_search_connection(
    source: str = Form(...),
    query: str = Form("test search"),
    tavily_api_key: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """测试搜索API连接"""
    try:
        if source == "duckduckgo":
            # DuckDuckGo 不需要 API Key，直接测试
            import requests
            params = {"q": query, "format": "json"}
            response = requests.get(
                "https://api.duckduckgo.com/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
        elif source == "tavily":
            if not tavily_api_key:
                setting = crud.get_setting(db, "tavily_api_key")
                tavily_api_key = setting.value if setting else None
                if not tavily_api_key:
                    raise HTTPException(status_code=400, detail="请提供Tavily API Key")
            
            import requests
            payload = {
                "api_key": tavily_api_key,
                "query": query,
                "max_results": 1
            }

            response = requests.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
        else:
            raise HTTPException(status_code=400, detail="不支持的搜索源")
        
        return {"success": True, "message": f"{source.title()} 搜索连接测试成功"}
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"搜索API连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@app.post("/test-api-connection")
def test_api_connection():
    """测试全局API连接"""
    try:
        if not ai_manager.is_configured():
            return {"success": False, "error": "请先配置API Key和API Base"}
        
        # 发送测试请求
        test_messages = [{"role": "user", "content": "Hello"}]
        result = ai_manager.chat(test_messages, stream=False)
        
        return {"success": True, "message": "API连接测试成功"}
    except Exception as e:
        return {"success": False, "error": f"API连接测试失败: {str(e)}"}


@app.post("/test-provider-connection")
def test_provider_connection(
    api_base: str = Form(...),
    api_key: str = Form(...),
    model: str = Form(...),
):
    """测试指定Provider的连接"""
    try:
        # 创建临时的AI管理器实例进行测试
        temp_manager = AIManager()
        temp_manager.set_provider(
            api_base=api_base,
            api_key=api_key,
            default_model=model
        )
        
        # 发送测试请求
        test_messages = [{"role": "user", "content": "Hello"}]
        result = temp_manager.chat(test_messages, stream=False)
        
        return {"success": True, "message": "Provider连接测试成功"}
    except Exception as e:
        return {"success": False, "error": f"Provider连接测试失败: {str(e)}"}


@app.get("/api-status")
def get_api_status():
    """获取API配置状态"""
    return {
        "configured": ai_manager.is_configured(),
        "api_base": ai_manager._provider.api_base,
        "has_api_key": bool(ai_manager._provider.api_key),
        "default_model": ai_manager._provider.default_model
    }


# ========== MCP服务器管理接口（新增） ==========


@app.get("/mcp/servers")
def list_mcp_servers(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    """获取MCP服务器列表"""
    servers = crud.list_mcp_servers(db, enabled_only=enabled_only)
    return [server.to_dict() for server in servers]


@app.post("/mcp/servers")
def create_mcp_server(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    connection_type: str = Form(...),  # "stdio" | "http"
    command: Optional[str] = Form(None),
    args: Optional[str] = Form(None),  # JSON字符串
    url: Optional[str] = Form(None),
    env_vars: Optional[str] = Form(None),  # JSON字符串
    is_enabled: bool = Form(True),
    db: Session = Depends(get_db),
):
    """创建MCP服务器配置"""
    # 验证连接类型
    if connection_type not in ["stdio", "http"]:
        raise HTTPException(status_code=400, detail="连接类型必须是 stdio 或 http")
    
    # 验证必要参数
    if connection_type == "stdio" and not command:
        raise HTTPException(status_code=400, detail="stdio类型必须提供command")
    if connection_type == "http" and not url:
        raise HTTPException(status_code=400, detail="http类型必须提供url")
    
    # 验证JSON格式
    if args:
        try:
            json.loads(args)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="args必须是有效的JSON格式")
    
    if env_vars:
        try:
            json.loads(env_vars)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="env_vars必须是有效的JSON格式")
    
    try:
        server = crud.create_mcp_server(
            db,
            name=name,
            description=description,
            connection_type=connection_type,
            command=command,
            args=args,
            url=url,
            env_vars=env_vars,
            is_enabled=is_enabled,
        )
        return server.to_dict()
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="MCP服务器名称已存在")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/servers/{server_id}")
def update_mcp_server(
    server_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    connection_type: Optional[str] = Form(None),
    command: Optional[str] = Form(None),
    args: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    env_vars: Optional[str] = Form(None),
    is_enabled: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
):
    """更新MCP服务器配置"""
    # 验证连接类型
    if connection_type and connection_type not in ["stdio", "http"]:
        raise HTTPException(status_code=400, detail="连接类型必须是 stdio 或 http")
    
    # 验证JSON格式
    if args:
        try:
            json.loads(args)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="args必须是有效的JSON格式")
    
    if env_vars:
        try:
            json.loads(env_vars)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="env_vars必须是有效的JSON格式")
    
    server = crud.update_mcp_server(
        db,
        server_id,
        name=name,
        description=description,
        connection_type=connection_type,
        command=command,
        args=args,
        url=url,
        env_vars=env_vars,
        is_enabled=is_enabled,
    )
    if not server:
        raise HTTPException(status_code=404, detail="MCP服务器不存在")
    return server.to_dict()


@app.delete("/mcp/servers/{server_id}")
def delete_mcp_server(server_id: int, db: Session = Depends(get_db)):
    """删除MCP服务器配置"""
    crud.delete_mcp_server(db, server_id)
    return {"success": True}


@app.post("/mcp/servers/{server_id}/test")
def test_mcp_server_connection(server_id: int, db: Session = Depends(get_db)):
    """测试MCP服务器连接"""
    server = crud.get_mcp_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP服务器不存在")
    
    # 这里可以实现实际的MCP连接测试逻辑
    # 目前返回模拟结果
    return {
        "success": True,
        "message": f"MCP服务器 {server.name} 连接测试成功",
        "server_info": {
            "name": server.name,
            "type": server.connection_type,
            "status": "connected" if server.is_enabled else "disabled"
        }
    }


@app.get("/mcp/servers/{server_id}/tools")
def get_mcp_server_tools(server_id: int, db: Session = Depends(get_db)):
    """获取MCP服务器提供的工具列表"""
    server = crud.get_mcp_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP服务器不存在")
    
    # 这里可以实现实际的MCP工具发现逻辑
    # 目前返回模拟数据
    mock_tools = [
        {
            "name": f"{server.name}_tool_1",
            "description": f"来自 {server.name} 的示例工具1",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "name": f"{server.name}_tool_2", 
            "description": f"来自 {server.name} 的示例工具2",
            "parameters": {"type": "object", "properties": {}}
        }
    ]
    
    return {
        "server_name": server.name,
        "tools": mock_tools
    }


# ========== 知识图谱接口 ==========

@app.get("/knowledge/graph/stats")
def get_knowledge_graph_stats(
    kb_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """获取知识图谱统计信息"""
    stats = crud.get_knowledge_graph_stats(db, kb_id)
    return stats


@app.get("/knowledge/graph/entities")
def list_knowledge_entities(
    kb_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """列出知识图谱实体"""
    entities = crud.list_entities(db, kb_id=kb_id, entity_type=entity_type, limit=limit)
    return [e.to_dict() for e in entities]


@app.get("/knowledge/graph/entities/search")
def search_knowledge_entities(
    query: str,
    kb_id: Optional[int] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """搜索知识图谱实体"""
    entities = crud.search_entities(db, query, kb_id=kb_id, limit=limit)
    return [e.to_dict() for e in entities]


@app.get("/knowledge/graph/entities/{entity_id}")
def get_knowledge_entity(
    entity_id: int,
    db: Session = Depends(get_db),
):
    """获取单个实体详情"""
    entity = crud.get_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity.to_dict()


@app.get("/knowledge/graph/entities/{entity_id}/relations")
def get_entity_relations(
    entity_id: int,
    max_depth: int = 2,
    db: Session = Depends(get_db),
):
    """获取实体的关系网络"""
    entity = crud.get_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    
    related = crud.get_related_entities(db, entity_id, max_depth=max_depth)
    
    return {
        "entity": entity.to_dict(),
        "related": [
            {
                "entity": item["entity"].to_dict(),
                "relation": item["relation"].to_dict(),
                "depth": item["depth"],
            }
            for item in related
        ]
    }


@app.get("/knowledge/graph/relations")
def list_knowledge_relations(
    kb_id: Optional[int] = None,
    entity_id: Optional[int] = None,
    relation_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """列出知识图谱关系"""
    relations = crud.list_relations(
        db, 
        kb_id=kb_id, 
        entity_id=entity_id, 
        relation_type=relation_type, 
        limit=limit
    )
    return [r.to_dict() for r in relations]


@app.post("/knowledge/graph/entities")
def create_knowledge_entity(
    kb_id: Optional[int] = Form(None),
    name: str = Form(...),
    entity_type: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """手动创建实体"""
    entity = crud.create_entity(
        db,
        kb_id=kb_id,
        name=name,
        entity_type=entity_type,
        description=description,
    )
    return entity.to_dict()


@app.post("/knowledge/graph/relations")
def create_knowledge_relation(
    kb_id: Optional[int] = Form(None),
    source_id: int = Form(...),
    target_id: int = Form(...),
    relation_type: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """手动创建关系"""
    # 验证实体存在
    source = crud.get_entity(db, source_id)
    target = crud.get_entity(db, target_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="源实体或目标实体不存在")
    
    relation = crud.create_relation(
        db,
        kb_id=kb_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        description=description,
    )
    return relation.to_dict()


@app.delete("/knowledge/graph/entities/{entity_id}")
def delete_knowledge_entity(entity_id: int, db: Session = Depends(get_db)):
    """删除实体（会级联删除相关关系）"""
    crud.delete_entity(db, entity_id)
    return {"success": True}


@app.delete("/knowledge/graph/relations/{relation_id}")
def delete_knowledge_relation(relation_id: int, db: Session = Depends(get_db)):
    """删除关系"""
    crud.delete_relation(db, relation_id)
    return {"success": True}


@app.get("/knowledge/graph/context")
def get_graph_context(
    query: str,
    kb_id: Optional[int] = None,
    max_entities: int = 5,
    db: Session = Depends(get_db),
):
    """基于查询获取知识图谱上下文（用于增强 RAG）"""
    from app.ai.knowledge_graph import search_graph_context
    context = search_graph_context(db, query, kb_id=kb_id, max_entities=max_entities)
    return {"context": context}


@app.get("/knowledge/embedding-models")
def get_embedding_models(db: Session = Depends(get_db)):
    """获取可用的向量模型列表 - 基于用户配置的Provider"""
    # 获取所有Provider
    providers = crud.list_providers(db)
    
    # 收集所有Provider中的向量模型
    embedding_models = set()
    
    # 添加全局默认向量模型
    embedding_models.update(settings.embedding_models)
    
    # 从Provider中提取可能的向量模型
    for provider in providers:
        if provider.models:
            provider_models = [m.strip() for m in provider.models.split(",") if m.strip()]
            # 过滤出向量模型（通常包含embedding关键字）
            for model in provider_models:
                if "embedding" in model.lower() or "embed" in model.lower():
                    embedding_models.add(model)
    
    # 如果没有找到任何向量模型，返回空列表
    if not embedding_models:
        return {
            "default": None,
            "models": [],
            "message": "当前Provider中未配置向量模型，请在Provider设置中添加向量模型"
        }
    
    return {
        "default": settings.EMBEDDING_MODEL if settings.EMBEDDING_MODEL in embedding_models else list(embedding_models)[0],
        "models": sorted(list(embedding_models)),
    }


@app.get("/models/vision")
def get_vision_models(db: Session = Depends(get_db)):
    """获取可用的视觉模型列表"""
    # 获取所有Provider
    providers = crud.list_providers(db)
    
    # 收集所有Provider中的视觉模型
    vision_models = set()
    
    # 从Provider中提取视觉模型
    for provider in providers:
        if provider.models:
            provider_models = [m.strip() for m in provider.models.split(",") if m.strip()]
            # 过滤出视觉模型（通常包含vision关键字或特定模型名）
            for model in provider_models:
                model_lower = model.lower()
                if "vision" in model_lower or "gpt-4o" in model_lower or "claude-3" in model_lower:
                    vision_models.add(model)
    
    return {
        "default": list(vision_models)[0] if vision_models else None,
        "models": sorted(list(vision_models)),
    }


@app.get("/models/rerank")
def get_rerank_models(db: Session = Depends(get_db)):
    """获取可用的重排模型列表"""
    # 获取所有Provider
    providers = crud.list_providers(db)
    
    # 收集所有Provider中的重排模型
    rerank_models = set()
    
    # 从Provider中提取重排模型
    for provider in providers:
        if provider.models:
            provider_models = [m.strip() for m in provider.models.split(",") if m.strip()]
            # 过滤出重排模型（通常包含rerank关键字）
            for model in provider_models:
                if "rerank" in model.lower():
                    rerank_models.add(model)
    
    return {
        "default": list(rerank_models)[0] if rerank_models else None,
        "models": sorted(list(rerank_models)),
    }


# ========== 静态页面 ==========


@app.get("/")
def index():
    # 返回新的分离后的前端页面
    from fastapi.responses import HTMLResponse

    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index_new.html")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        # 如果新文件不存在，回退到原文件
        frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
        frontend_path = os.path.abspath(frontend_path)
        if not os.path.exists(frontend_path):
            return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
    
    with open(frontend_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)

@app.get("/style.css")
def get_css():
    # 返回CSS文件
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "style.css")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        raise HTTPException(status_code=404, detail="CSS file not found")
    return FileResponse(frontend_path, media_type="text/css")

@app.get("/script.js")
def get_js():
    # 返回JavaScript文件
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "script.js")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        raise HTTPException(status_code=404, detail="JavaScript file not found")
    return FileResponse(frontend_path, media_type="application/javascript")

@app.get("/markdown.js")
def get_markdown_js():
    # 返回Markdown渲染JavaScript文件
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "markdown.js")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        raise HTTPException(status_code=404, detail="Markdown JavaScript file not found")
    return FileResponse(frontend_path, media_type="application/javascript")

@app.get("/favicon.ico")
def get_favicon():
    # 返回favicon文件
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "favicon.ico")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        # 如果没有favicon文件，返回一个简单的响应
        from fastapi.responses import Response
        return Response(content="", media_type="image/x-icon")
    return FileResponse(frontend_path, media_type="image/x-icon")

@app.get("/render-logger.js")
def get_render_logger_js():
    # 返回渲染日志JavaScript文件
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "render-logger.js")
    frontend_path = os.path.abspath(frontend_path)
    if not os.path.exists(frontend_path):
        raise HTTPException(status_code=404, detail="Render logger JavaScript file not found")
    return FileResponse(frontend_path, media_type="application/javascript")

# 前端日志接收API
@app.post("/api/frontend-log")
async def receive_frontend_log(log_entry: dict):
    """接收前端日志并写入文件"""
    import datetime
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    log_file = os.path.join(log_dir, "frontend-render.log")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            timestamp = log_entry.get("timestamp", datetime.datetime.now().isoformat())
            level = log_entry.get("level", "info").upper()
            category = log_entry.get("category", "UNKNOWN")
            message = log_entry.get("message", "")
            data = log_entry.get("data", "")
            session_id = log_entry.get("sessionId", "")
            
            log_line = f"{timestamp} [{level}][{category}][{session_id}] {message}"
            if data:
                log_line += f" | {data}"
            f.write(log_line + "\n")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/frontend-log/batch")
async def receive_frontend_logs_batch(data: dict):
    """批量接收前端日志"""
    import datetime
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    log_file = os.path.join(log_dir, "frontend-render.log")
    
    logs = data.get("logs", [])
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            for log_entry in logs:
                timestamp = log_entry.get("timestamp", datetime.datetime.now().isoformat())
                level = log_entry.get("level", "info").upper()
                category = log_entry.get("category", "UNKNOWN")
                message = log_entry.get("message", "")
                log_data = log_entry.get("data", "")
                session_id = log_entry.get("sessionId", "")
                
                log_line = f"{timestamp} [{level}][{category}][{session_id}] {message}"
                if log_data:
                    log_line += f" | {log_data}"
                f.write(log_line + "\n")
        return {"status": "ok", "count": len(logs)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
