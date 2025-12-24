# app/ai/tools.py
import json
import textwrap
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import SessionLocal
from app.core.config import settings


# 已有：本地工具定义 -------------------------------------------------


def get_local_time_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_local_time",
            "description": "获取当前服务器的本地时间。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


def run_get_local_time_tool() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_calculator_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "calculate_expression",
            "description": "计算一个简单的数学表达式，例如 1+2*3。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "需要计算的数学表达式，例如 '1+2*3'",
                    }
                },
                "required": ["expression"],
            },
        },
    }


def run_calculator_tool(expression: str) -> str:
    # 简单 eval，仅示例，生产环境要加沙盒
    try:
        value = eval(expression, {"__builtins__": {}})
    except Exception as e:
        return f"表达式计算错误: {e}"
    return str(value)


# === 新增：知识库检索工具定义 ====================================


def search_knowledge_tool_schema() -> Dict[str, Any]:
    """
    OpenAI tools schema: 知识库检索工具定义。
    """
    return {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在已构建的本地知识库中检索与当前问题相关的文本片段，用于增强回答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户问题或需要检索的内容，用于生成向量检索。",
                    },
                    "kb_id": {
                        "type": "integer",
                        "description": "可选，指定要检索的知识库 ID，不填则使用默认知识库。",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回最多多少条匹配结果，默认 5。",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    }


def run_search_knowledge_tool(
    *,
    query: str,
    kb_id: Optional[int] = None,
    top_k: int = 5,
    embedding_fn=None,
    use_graph: bool = True,  # 新增：是否使用知识图谱增强
) -> str:
    """
    知识库检索工具的实际执行逻辑：

    1. 使用 embedding_fn(query) 生成 query 向量；
    2. 用 crud.search_knowledge_chunks 在 DB 中做向量相似度检索；
    3. （可选）从知识图谱中获取相关实体和关系；
    4. 把检索到的内容拼成一段说明文字返回给大模型。

    embedding_fn: 一个函数，签名类似：
        embedding_fn([text: str]) -> List[List[float]]
    由调用方传入（通常是 AIManager.create_embedding）。
    """
    parts: List[str] = []
    db: Session = SessionLocal()
    
    try:
        # 1. 知识图谱检索（如果启用）
        if use_graph:
            try:
                from app.ai.knowledge_graph import search_graph_context
                graph_context = search_graph_context(db, query, kb_id=kb_id, max_entities=3)
                if graph_context:
                    parts.append(graph_context)
            except Exception as e:
                print(f"知识图谱检索失败: {e}")
        
        # 2. 向量检索
        if embedding_fn is not None:
            embeddings = embedding_fn([query])
            if embeddings:
                query_embedding = embeddings[0]
                chunks = crud.search_knowledge_chunks(
                    db,
                    query_embedding=query_embedding,
                    kb_id=kb_id,
                    top_k=top_k,
                )
                
                if chunks:
                    parts.append("\n【向量检索结果】")
                    for idx, chunk in enumerate(chunks, start=1):
                        doc = chunk.document
                        kb_name = doc.kb.name if doc and doc.kb else settings.KNOWLEDGE_DEFAULT_KB_NAME
                        parts.append(
                            textwrap.dedent(
                                f"""
                                [片段 {idx} | 知识库: {kb_name} | 文档: {doc.file_name if doc else '未知'}]
                                {chunk.content}
                                """
                            ).strip()
                        )
    finally:
        db.close()

    if not parts:
        return "知识库中没有找到与当前问题足够相关的内容。"

    return "\n\n".join(parts)


# === 新增：联网搜索工具定义 ====================================

def web_search_tool_schema() -> Dict[str, Any]:
    """
    OpenAI tools schema: 联网搜索工具定义。
    """
    return {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在互联网上搜索最新信息，获取实时数据和最新资讯。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题，用于在互联网上查找相关信息。",
                    },
                    "source": {
                        "type": "string",
                        "description": "搜索源：duckduckgo（免费，默认）、tavily（需API Key）",
                        "enum": ["duckduckgo", "tavily"],
                        "default": "duckduckgo"
                    },
                },
                "required": ["query"],
            },
        },
    }


def _search_with_duckduckgo(query: str) -> str:
    """
    使用 DuckDuckGo 搜索（免费，无需 API Key）
    """
    import requests
    import json
    
    try:
        # DuckDuckGo Instant Answer API
        url = "https://api.duckduckgo.com/"
        params = {
            'q': query,
            'format': 'json',
            'no_html': 1,
            'skip_disambig': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            results = []
            
            # 获取摘要答案
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", "摘要"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", "")
                })
            
            # 获取相关主题
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:50] + "...",
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            
            if not results:
                # 如果 Instant Answer 没有结果，使用 HTML 搜索作为备选
                return _search_duckduckgo_html(query)
            
            return json.dumps({
                "query": query,
                "source": "duckduckgo",
                "results": results[:3]
            }, ensure_ascii=False, indent=2)
        else:
            return _search_duckduckgo_html(query)
            
    except Exception as e:
        return f"DuckDuckGo搜索失败: {str(e)}"


def _search_duckduckgo_html(query: str) -> str:
    """
    DuckDuckGo HTML 搜索备选方案
    """
    import requests
    import json
    import re
    
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        data = {'q': query}
        
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            html = response.text
            
            # 简单解析结果
            results = []
            # 匹配结果链接和标题
            pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            
            # 匹配摘要
            snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
            snippets = re.findall(snippet_pattern, html)
            
            for i, (url, title) in enumerate(matches[:3]):
                snippet = snippets[i] if i < len(snippets) else ""
                results.append({
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippet.strip()
                })
            
            if results:
                return json.dumps({
                    "query": query,
                    "source": "duckduckgo",
                    "results": results
                }, ensure_ascii=False, indent=2)
            else:
                return f"搜索关键词：{query}\n\n未找到相关结果。"
        else:
            return f"DuckDuckGo搜索失败，状态码: {response.status_code}"
            
    except Exception as e:
        return f"DuckDuckGo搜索失败: {str(e)}"


def _search_with_tavily(query: str) -> str:
    """
    使用 Tavily 搜索（需要 API Key）
    """
    import requests
    import json
    
    try:
        # 从数据库获取 API Key
        tavily_api_key = None
        try:
            db = SessionLocal()
            setting = crud.get_setting(db, "tavily_api_key")
            tavily_api_key = setting.value if setting else None
            db.close()
        except:
            pass
        
        if not tavily_api_key:
            return f"未配置 Tavily API Key，已自动切换到 DuckDuckGo 搜索。\n\n" + _search_with_duckduckgo(query)
        
        # Tavily API 调用
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False,
            "max_results": 5
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return f"搜索关键词：{query}\n\n未找到相关结果。"
            
            formatted_results = []
            for result in results[:3]:
                formatted_results.append({
                    "title": result.get("title", "无标题"),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "无内容")[:200]
                })
            
            return json.dumps({
                "query": query,
                "source": "tavily",
                "results": formatted_results
            }, ensure_ascii=False, indent=2)
        else:
            return f"Tavily搜索失败，状态码: {response.status_code}"
            
    except Exception as e:
        return f"Tavily搜索失败: {str(e)}"


def run_web_search_tool(
    *,
    query: str,
    source: str = "duckduckgo",
    db_session=None,
) -> str:
    """
    联网搜索工具的实际执行逻辑
    """
    try:
        if source == "duckduckgo":
            return _search_with_duckduckgo(query)
        elif source == "tavily":
            return _search_with_tavily(query)
        else:
            # 默认使用 DuckDuckGo
            return _search_with_duckduckgo(query)
    except Exception as e:
        return f"搜索失败: {str(e)}"


# 统一对外接口：根据开关组合返回工具列表 -----------------------------

def get_tools(
    *,
    enable_knowledge_base: bool = False,
    enable_mcp: bool = False,
    enable_web_search: bool = False,
) -> List[Dict[str, Any]]:
    """
    根据功能开关返回需要注册给 OpenAI 的 tools 列表。

    - enable_knowledge_base: 是否启用知识库检索工具 search_knowledge
    - enable_mcp: MCP 相关工具预留（暂未实现）
    - enable_web_search: 是否启用联网搜索工具 web_search
    """
    tools: List[Dict[str, Any]] = []

    # 知识库工具
    if enable_knowledge_base:
        tools.append(search_knowledge_tool_schema())

    # 联网搜索工具
    if enable_web_search:
        tools.append(web_search_tool_schema())

    # MCP 工具（预留）
    if enable_mcp:
        pass

    return tools
